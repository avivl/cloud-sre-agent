"""Performance dashboards and visualization system."""

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any

from ..logging import get_logger

logger = get_logger(__name__)


class WidgetType(Enum):
    """Types of dashboard widgets."""

    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    GAUGE = "gauge"
    TABLE = "table"
    METRIC_CARD = "metric_card"
    HEATMAP = "heatmap"


@dataclass
class DashboardConfig:
    """Configuration for performance dashboards.
    
    Attributes:
        refresh_interval: Dashboard refresh interval in seconds
        max_data_points: Maximum number of data points per widget
        enable_real_time: Whether to enable real-time updates
        enable_historical_data: Whether to enable historical data
        data_retention: How long to keep historical data in seconds
        default_widget_size: Default widget size
    """

    refresh_interval: float = 5.0
    max_data_points: int = 1000
    enable_real_time: bool = True
    enable_historical_data: bool = True
    data_retention: float = 3600.0  # 1 hour
    default_widget_size: str = "medium"


@dataclass
class DashboardWidget:
    """Dashboard widget definition.
    
    Attributes:
        id: Unique widget identifier
        title: Widget title
        widget_type: Type of widget
        data_source: Data source for the widget
        config: Widget-specific configuration
        position: Widget position (x, y, width, height)
        refresh_interval: Widget refresh interval in seconds
        enabled: Whether the widget is enabled
    """

    id: str
    title: str
    widget_type: WidgetType
    data_source: str
    config: dict[str, Any] = field(default_factory=dict)
    position: dict[str, int] = field(
        default_factory=lambda: {"x": 0, "y": 0, "width": 4, "height": 3}
    )
    refresh_interval: float = 5.0
    enabled: bool = True


@dataclass
class PerformanceVisualization:
    """Performance visualization data.
    
    Attributes:
        widget_id: Widget identifier
        data: Visualization data
        timestamp: When the data was generated
        metadata: Additional metadata
    """

    widget_id: str
    data: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class PerformanceDashboard:
    """Performance dashboard and visualization system.
    
    Provides real-time performance visualizations and
    historical trend analysis for system monitoring.
    """

    def __init__(self, config: DashboardConfig | None = None):
        """Initialize the performance dashboard.
        
        Args:
            config: Dashboard configuration
        """
        self._config = config or DashboardConfig()
        self._lock = asyncio.Lock()
        self._widgets: dict[str, DashboardWidget] = {}
        self._widget_data: dict[str, deque] = {}
        self._data_sources: dict[str, Callable[[], Any]] = {}
        self._refresh_tasks: dict[str, asyncio.Task] = {}
        self._cleanup_task: asyncio.Task | None = None
        self._start_cleanup_task()

    def _start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_old_data())

    async def _cleanup_old_data(self) -> None:
        """Clean up old data based on retention period."""
        while True:
            try:
                current_time = time.time()
                cutoff_time = current_time - self._config.data_retention

                async with self._lock:
                    for widget_id, data_deque in self._widget_data.items():
                        # Remove old data points
                        while data_deque and data_deque[0].timestamp < cutoff_time:
                            data_deque.popleft()

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Error in dashboard cleanup task: {e}")
                await asyncio.sleep(60)

    def add_widget(self, widget: DashboardWidget) -> None:
        """Add a dashboard widget.
        
        Args:
            widget: Widget to add
        """
        asyncio.create_task(self._add_widget_async(widget))

    async def _add_widget_async(self, widget: DashboardWidget) -> None:
        """Add a dashboard widget asynchronously.
        
        Args:
            widget: Widget to add
        """
        async with self._lock:
            self._widgets[widget.id] = widget
            self._widget_data[widget.id] = deque(maxlen=self._config.max_data_points)

            # Start refresh task if real-time is enabled
            if self._config.enable_real_time and widget.enabled:
                self._refresh_tasks[widget.id] = asyncio.create_task(
                    self._refresh_widget_data(widget.id)
                )

    def remove_widget(self, widget_id: str) -> None:
        """Remove a dashboard widget.
        
        Args:
            widget_id: ID of the widget to remove
        """
        asyncio.create_task(self._remove_widget_async(widget_id))

    async def _remove_widget_async(self, widget_id: str) -> None:
        """Remove a dashboard widget asynchronously.
        
        Args:
            widget_id: ID of the widget to remove
        """
        async with self._lock:
            # Cancel refresh task
            if widget_id in self._refresh_tasks:
                self._refresh_tasks[widget_id].cancel()
                del self._refresh_tasks[widget_id]

            # Remove widget and data
            self._widgets.pop(widget_id, None)
            self._widget_data.pop(widget_id, None)

    def register_data_source(self, name: str, data_source: Callable[[], Any]) -> None:
        """Register a data source.
        
        Args:
            name: Name of the data source
            data_source: Function that returns data for the widget
        """
        self._data_sources[name] = data_source

    async def _refresh_widget_data(self, widget_id: str) -> None:
        """Refresh widget data periodically.
        
        Args:
            widget_id: ID of the widget to refresh
        """
        while True:
            try:
                widget = self._widgets.get(widget_id)
                if not widget or not widget.enabled:
                    break

                # Get data from data source
                data_source = self._data_sources.get(widget.data_source)
                if data_source:
                    data = data_source()

                    # Create visualization data
                    visualization = PerformanceVisualization(
                        widget_id=widget_id,
                        data=data,
                        metadata={"widget_type": widget.widget_type.value}
                    )

                    # Store data
                    async with self._lock:
                        if widget_id in self._widget_data:
                            self._widget_data[widget_id].append(visualization)

                await asyncio.sleep(widget.refresh_interval)

            except Exception as e:
                logger.error(f"Error refreshing widget {widget_id}: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    def get_widget_data(
        self,
        widget_id: str,
        limit: int | None = None
    ) -> list[PerformanceVisualization]:
        """Get data for a specific widget.
        
        Args:
            widget_id: ID of the widget
            limit: Maximum number of data points to return
            
        Returns:
            List of visualization data
        """
        async def _get_data():
            async with self._lock:
                data = list(self._widget_data.get(widget_id, []))
                if limit:
                    data = data[-limit:]
                return data

        return asyncio.run(_get_data())

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get data for all widgets in the dashboard.
        
        Returns:
            Dashboard data
        """
        async def _get_dashboard_data():
            async with self._lock:
                dashboard_data = {}
                for widget_id, widget in self._widgets.items():
                    if widget.enabled:
                        data = list(self._widget_data.get(widget_id, []))
                        dashboard_data[widget_id] = {
                            "widget": {
                                "id": widget.id,
                                "title": widget.title,
                                "type": widget.widget_type.value,
                                "position": widget.position,
                                "config": widget.config
                            },
                            "data": [
                                {
                                    "timestamp": viz.timestamp,
                                    "data": viz.data,
                                    "metadata": viz.metadata
                                }
                                for viz in data
                            ]
                        }
                return dashboard_data

        return asyncio.run(_get_dashboard_data())

    def create_metric_card_widget(
        self,
        widget_id: str,
        title: str,
        metric_name: str,
        data_source: str,
        position: dict[str, int] | None = None
    ) -> DashboardWidget:
        """Create a metric card widget.
        
        Args:
            widget_id: Unique widget identifier
            title: Widget title
            metric_name: Name of the metric to display
            data_source: Data source name
            position: Widget position
            
        Returns:
            Dashboard widget
        """
        return DashboardWidget(
            id=widget_id,
            title=title,
            widget_type=WidgetType.METRIC_CARD,
            data_source=data_source,
            config={"metric_name": metric_name},
            position=position or {"x": 0, "y": 0, "width": 2, "height": 2}
        )

    def create_line_chart_widget(
        self,
        widget_id: str,
        title: str,
        metric_name: str,
        data_source: str,
        position: dict[str, int] | None = None
    ) -> DashboardWidget:
        """Create a line chart widget.
        
        Args:
            widget_id: Unique widget identifier
            title: Widget title
            metric_name: Name of the metric to display
            data_source: Data source name
            position: Widget position
            
        Returns:
            Dashboard widget
        """
        return DashboardWidget(
            id=widget_id,
            title=title,
            widget_type=WidgetType.LINE_CHART,
            data_source=data_source,
            config={"metric_name": metric_name, "x_axis": "timestamp", "y_axis": "value"},
            position=position or {"x": 0, "y": 0, "width": 6, "height": 4}
        )

    def create_gauge_widget(
        self,
        widget_id: str,
        title: str,
        metric_name: str,
        data_source: str,
        min_value: float = 0.0,
        max_value: float = 100.0,
        position: dict[str, int] | None = None
    ) -> DashboardWidget:
        """Create a gauge widget.
        
        Args:
            widget_id: Unique widget identifier
            title: Widget title
            metric_name: Name of the metric to display
            data_source: Data source name
            min_value: Minimum value for the gauge
            max_value: Maximum value for the gauge
            position: Widget position
            
        Returns:
            Dashboard widget
        """
        return DashboardWidget(
            id=widget_id,
            title=title,
            widget_type=WidgetType.GAUGE,
            data_source=data_source,
            config={
                "metric_name": metric_name,
                "min_value": min_value,
                "max_value": max_value
            },
            position=position or {"x": 0, "y": 0, "width": 3, "height": 3}
        )

    def create_table_widget(
        self,
        widget_id: str,
        title: str,
        data_source: str,
        columns: list[str],
        position: dict[str, int] | None = None
    ) -> DashboardWidget:
        """Create a table widget.
        
        Args:
            widget_id: Unique widget identifier
            title: Widget title
            data_source: Data source name
            columns: List of column names
            position: Widget position
            
        Returns:
            Dashboard widget
        """
        return DashboardWidget(
            id=widget_id,
            title=title,
            widget_type=WidgetType.TABLE,
            data_source=data_source,
            config={"columns": columns},
            position=position or {"x": 0, "y": 0, "width": 8, "height": 6}
        )

    def export_dashboard_config(self) -> dict[str, Any]:
        """Export dashboard configuration.
        
        Returns:
            Dashboard configuration
        """
        async def _export_config():
            async with self._lock:
                return {
                    "config": {
                        "refresh_interval": self._config.refresh_interval,
                        "max_data_points": self._config.max_data_points,
                        "enable_real_time": self._config.enable_real_time,
                        "enable_historical_data": self._config.enable_historical_data,
                        "data_retention": self._config.data_retention
                    },
                    "widgets": [
                        {
                            "id": widget.id,
                            "title": widget.title,
                            "type": widget.widget_type.value,
                            "data_source": widget.data_source,
                            "config": widget.config,
                            "position": widget.position,
                            "refresh_interval": widget.refresh_interval,
                            "enabled": widget.enabled
                        }
                        for widget in self._widgets.values()
                    ]
                }

        return asyncio.run(_export_config())

    def import_dashboard_config(self, config: dict[str, Any]) -> None:
        """Import dashboard configuration.
        
        Args:
            config: Dashboard configuration to import
        """
        asyncio.create_task(self._import_dashboard_config_async(config))

    async def _import_dashboard_config_async(self, config: dict[str, Any]) -> None:
        """Import dashboard configuration asynchronously.
        
        Args:
            config: Dashboard configuration to import
        """
        async with self._lock:
            # Clear existing widgets
            for widget_id in list(self._widgets.keys()):
                await self._remove_widget_async(widget_id)

            # Import widgets
            for widget_config in config.get("widgets", []):
                widget = DashboardWidget(
                    id=widget_config["id"],
                    title=widget_config["title"],
                    widget_type=WidgetType(widget_config["type"]),
                    data_source=widget_config["data_source"],
                    config=widget_config.get("config", {}),
                    position=widget_config.get(
                        "position", {"x": 0, "y": 0, "width": 4, "height": 3}
                    ),
                    refresh_interval=widget_config.get("refresh_interval", 5.0),
                    enabled=widget_config.get("enabled", True)
                )
                await self._add_widget_async(widget)

    def get_dashboard_summary(self) -> dict[str, Any]:
        """Get dashboard summary.
        
        Returns:
            Dashboard summary
        """
        async def _get_summary():
            async with self._lock:
                total_widgets = len(self._widgets)
                enabled_widgets = sum(1 for widget in self._widgets.values() if widget.enabled)
                total_data_points = sum(len(data) for data in self._widget_data.values())

                return {
                    "total_widgets": total_widgets,
                    "enabled_widgets": enabled_widgets,
                    "total_data_points": total_data_points,
                    "active_refresh_tasks": len(self._refresh_tasks),
                    "data_sources": list(self._data_sources.keys()),
                    "config": {
                        "refresh_interval": self._config.refresh_interval,
                        "max_data_points": self._config.max_data_points,
                        "enable_real_time": self._config.enable_real_time,
                        "enable_historical_data": self._config.enable_historical_data,
                        "data_retention": self._config.data_retention
                    }
                }

        return asyncio.run(_get_summary())

    def __enter__(self):
        """Context manager entry.
        
        Returns:
            Self
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit.
        
        Args:
            exc_type: Exception type
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()

        # Cancel all refresh tasks
        for task in self._refresh_tasks.values():
            if not task.done():
                task.cancel()
