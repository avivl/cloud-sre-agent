# gemini_sre_agent/source_control/error_handling/classification_metrics.py

"""
Classification metrics and performance measurement for error classification.

This module provides comprehensive metrics collection and analysis for
classification performance including confusion matrices, accuracy metrics,
and classification reports.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .classification_algorithms import ClassificationResult
from .core import ErrorType

logger = logging.getLogger(__name__)


@dataclass
class ConfusionMatrix:
    """Confusion matrix for classification evaluation."""

    true_positive: int = 0
    false_positive: int = 0
    true_negative: int = 0
    false_negative: int = 0
    matrix: Dict[Tuple[ErrorType, ErrorType], int] = field(default_factory=dict)
    classes: List[ErrorType] = field(default_factory=list)

    def add_prediction(self, true_label: ErrorType, predicted_label: ErrorType) -> None:
        """Add a prediction to the confusion matrix."""
        if true_label not in self.classes:
            self.classes.append(true_label)
        if predicted_label not in self.classes:
            self.classes.append(predicted_label)

        # Update matrix
        key = (true_label, predicted_label)
        self.matrix[key] = self.matrix.get(key, 0) + 1

        # Update binary classification metrics (for primary class)
        if true_label == predicted_label:
            self.true_positive += 1
        else:
            self.false_positive += 1
            self.false_negative += 1

    def get_matrix_array(self) -> np.ndarray:
        """Get confusion matrix as numpy array."""
        n_classes = len(self.classes)
        matrix_array = np.zeros((n_classes, n_classes), dtype=int)

        for i, true_label in enumerate(self.classes):
            for j, pred_label in enumerate(self.classes):
                key = (true_label, pred_label)
                matrix_array[i, j] = self.matrix.get(key, 0)

        return matrix_array

    def get_class_metrics(self, error_type: ErrorType) -> Dict[str, float]:
        """Get metrics for a specific error type."""
        if error_type not in self.classes:
            return {"precision": 0.0, "recall": 0.0, "f1_score": 0.0}

        tp = self.matrix.get((error_type, error_type), 0)
        fp = sum(
            self.matrix.get((other, error_type), 0)
            for other in self.classes
            if other != error_type
        )
        fn = sum(
            self.matrix.get((error_type, other), 0)
            for other in self.classes
            if other != error_type
        )

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_score = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        return {
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "support": tp + fn,
        }

    def get_overall_accuracy(self) -> float:
        """Get overall classification accuracy."""
        correct = sum(self.matrix.get((cls, cls), 0) for cls in self.classes)
        total = sum(self.matrix.values())
        return correct / total if total > 0 else 0.0


@dataclass
class ClassificationMetrics:
    """Comprehensive classification metrics."""

    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    macro_precision: float = 0.0
    macro_recall: float = 0.0
    macro_f1_score: float = 0.0
    weighted_precision: float = 0.0
    weighted_recall: float = 0.0
    weighted_f1_score: float = 0.0
    support: int = 0
    per_class_metrics: Dict[ErrorType, Dict[str, float]] = field(default_factory=dict)
    confusion_matrix: Optional[ConfusionMatrix] = None


@dataclass
class PerformanceMetrics:
    """Performance metrics for classification operations."""

    total_predictions: int = 0
    correct_predictions: int = 0
    average_confidence: float = 0.0
    average_prediction_time_ms: float = 0.0
    total_prediction_time_ms: float = 0.0
    classification_counts: Dict[ErrorType, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    confidence_by_type: Dict[ErrorType, List[float]] = field(
        default_factory=lambda: defaultdict(list)
    )


@dataclass
class MetricsSummary:
    """Summary of all classification metrics."""

    timestamp: float
    classification_metrics: ClassificationMetrics
    performance_metrics: PerformanceMetrics
    algorithm_name: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class ClassificationMetricsCollector:
    """Collector for classification performance metrics."""

    def __init__(self, name: str = "metrics_collector") -> None:
        """Initialize the metrics collector."""
        self.name = name
        self.logger = logging.getLogger(f"ClassificationMetricsCollector.{name}")

        # Metrics storage
        self.confusion_matrix = ConfusionMatrix()
        self.performance_metrics = PerformanceMetrics()
        self.prediction_history: List[Tuple[ErrorType, ErrorType, float, float]] = []

        # Time tracking
        self.start_time = time.time()

        self.logger.info(f"Initialized metrics collector: {name}")

    def record_prediction(
        self,
        true_label: ErrorType,
        predicted_result: ClassificationResult,
        prediction_time_ms: float,
    ) -> None:
        """Record a prediction for metrics calculation."""
        predicted_label = predicted_result.error_type
        confidence = predicted_result.confidence

        # Update confusion matrix
        self.confusion_matrix.add_prediction(true_label, predicted_label)

        # Update performance metrics
        self.performance_metrics.total_predictions += 1
        if true_label == predicted_label:
            self.performance_metrics.correct_predictions += 1

        # Update confidence tracking
        self.performance_metrics.classification_counts[predicted_label] += 1
        self.performance_metrics.confidence_by_type[predicted_label].append(confidence)

        # Update timing metrics
        self.performance_metrics.total_prediction_time_ms += prediction_time_ms

        # Update running averages
        total_conf = (
            self.performance_metrics.average_confidence
            * (self.performance_metrics.total_predictions - 1)
            + confidence
        )
        self.performance_metrics.average_confidence = (
            total_conf / self.performance_metrics.total_predictions
        )

        total_time = self.performance_metrics.total_prediction_time_ms
        self.performance_metrics.average_prediction_time_ms = (
            total_time / self.performance_metrics.total_predictions
        )

        # Store prediction history
        self.prediction_history.append(
            (true_label, predicted_label, confidence, prediction_time_ms)
        )

        self.logger.debug(
            f"Recorded prediction: {true_label} -> {predicted_label} "
            f"(confidence: {confidence:.3f}, time: {prediction_time_ms:.2f}ms)"
        )

    def calculate_classification_metrics(self) -> ClassificationMetrics:
        """Calculate comprehensive classification metrics."""
        if self.performance_metrics.total_predictions == 0:
            return ClassificationMetrics()

        # Calculate overall accuracy
        accuracy = self.confusion_matrix.get_overall_accuracy()

        # Calculate per-class metrics
        per_class_metrics = {}
        total_support = 0
        weighted_precision = 0.0
        weighted_recall = 0.0
        weighted_f1 = 0.0

        macro_precision_sum = 0.0
        macro_recall_sum = 0.0
        macro_f1_sum = 0.0

        for error_type in self.confusion_matrix.classes:
            class_metrics = self.confusion_matrix.get_class_metrics(error_type)
            per_class_metrics[error_type] = class_metrics

            support = class_metrics["support"]
            total_support += support

            # Weighted averages
            weighted_precision += class_metrics["precision"] * support
            weighted_recall += class_metrics["recall"] * support
            weighted_f1 += class_metrics["f1_score"] * support

            # Macro averages
            macro_precision_sum += class_metrics["precision"]
            macro_recall_sum += class_metrics["recall"]
            macro_f1_sum += class_metrics["f1_score"]

        # Finalize weighted averages
        if total_support > 0:
            weighted_precision /= total_support
            weighted_recall /= total_support
            weighted_f1 /= total_support

        # Finalize macro averages
        num_classes = len(self.confusion_matrix.classes)
        if num_classes > 0:
            macro_precision = macro_precision_sum / num_classes
            macro_recall = macro_recall_sum / num_classes
            macro_f1 = macro_f1_sum / num_classes
        else:
            macro_precision = macro_recall = macro_f1 = 0.0

        # Calculate overall precision, recall, F1 (micro-averaged)
        total_tp = sum(
            self.confusion_matrix.matrix.get((cls, cls), 0)
            for cls in self.confusion_matrix.classes
        )
        total_fp = sum(
            self.confusion_matrix.matrix.get((true_cls, pred_cls), 0)
            for true_cls in self.confusion_matrix.classes
            for pred_cls in self.confusion_matrix.classes
            if true_cls != pred_cls
        )
        total_fn = total_fp  # In multi-class, FP for one class is FN for others

        precision = (
            total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
        )
        recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
        f1_score = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        return ClassificationMetrics(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            macro_precision=macro_precision,
            macro_recall=macro_recall,
            macro_f1_score=macro_f1,
            weighted_precision=weighted_precision,
            weighted_recall=weighted_recall,
            weighted_f1_score=weighted_f1,
            support=int(total_support),
            per_class_metrics=per_class_metrics,
            confusion_matrix=self.confusion_matrix,
        )

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a comprehensive performance summary."""
        classification_metrics = self.calculate_classification_metrics()

        # Calculate confidence statistics by type
        confidence_stats = {}
        for (
            error_type,
            confidences,
        ) in self.performance_metrics.confidence_by_type.items():
            if confidences:
                confidence_stats[error_type.value] = {
                    "mean": np.mean(confidences),
                    "std": np.std(confidences),
                    "min": np.min(confidences),
                    "max": np.max(confidences),
                    "median": np.median(confidences),
                    "count": len(confidences),
                }

        # Calculate prediction distribution
        total_predictions = self.performance_metrics.total_predictions
        prediction_distribution = {}
        for error_type, count in self.performance_metrics.classification_counts.items():
            prediction_distribution[error_type.value] = {
                "count": count,
                "percentage": (
                    (count / total_predictions * 100) if total_predictions > 0 else 0.0
                ),
            }

        return {
            "classification_metrics": {
                "accuracy": classification_metrics.accuracy,
                "precision": classification_metrics.precision,
                "recall": classification_metrics.recall,
                "f1_score": classification_metrics.f1_score,
                "macro_precision": classification_metrics.macro_precision,
                "macro_recall": classification_metrics.macro_recall,
                "macro_f1_score": classification_metrics.macro_f1_score,
                "weighted_precision": classification_metrics.weighted_precision,
                "weighted_recall": classification_metrics.weighted_recall,
                "weighted_f1_score": classification_metrics.weighted_f1_score,
                "support": classification_metrics.support,
            },
            "performance_metrics": {
                "total_predictions": self.performance_metrics.total_predictions,
                "correct_predictions": self.performance_metrics.correct_predictions,
                "average_confidence": self.performance_metrics.average_confidence,
                "average_prediction_time_ms": self.performance_metrics.average_prediction_time_ms,
                "total_prediction_time_ms": self.performance_metrics.total_prediction_time_ms,
            },
            "confidence_statistics": confidence_stats,
            "prediction_distribution": prediction_distribution,
            "per_class_metrics": {
                error_type.value: metrics
                for error_type, metrics in classification_metrics.per_class_metrics.items()
            },
            "confusion_matrix": {
                "classes": (
                    [
                        cls.value
                        for cls in classification_metrics.confusion_matrix.classes
                    ]
                    if classification_metrics.confusion_matrix
                    else []
                ),
                "matrix": (
                    classification_metrics.confusion_matrix.get_matrix_array().tolist()
                    if classification_metrics.confusion_matrix
                    else []
                ),
            },
            "collection_metadata": {
                "collector_name": self.name,
                "collection_start_time": self.start_time,
                "collection_duration_s": time.time() - self.start_time,
                "num_classes": (
                    len(classification_metrics.confusion_matrix.classes)
                    if classification_metrics.confusion_matrix
                    else 0
                ),
            },
        }

    def generate_classification_report(self) -> str:
        """Generate a detailed classification report."""
        classification_metrics = self.calculate_classification_metrics()

        report_lines = [
            f"\nClassification Report - {self.name}",
            "=" * 60,
            "",
            "Overall Metrics:",
            f"  Accuracy:     {classification_metrics.accuracy:.4f}",
            f"  Precision:    {classification_metrics.precision:.4f}",
            f"  Recall:       {classification_metrics.recall:.4f}",
            f"  F1-Score:     {classification_metrics.f1_score:.4f}",
            "",
            "Macro Averages:",
            f"  Precision:    {classification_metrics.macro_precision:.4f}",
            f"  Recall:       {classification_metrics.macro_recall:.4f}",
            f"  F1-Score:     {classification_metrics.macro_f1_score:.4f}",
            "",
            "Weighted Averages:",
            f"  Precision:    {classification_metrics.weighted_precision:.4f}",
            f"  Recall:       {classification_metrics.weighted_recall:.4f}",
            f"  F1-Score:     {classification_metrics.weighted_f1_score:.4f}",
            "",
            "Performance Metrics:",
            f"  Total Predictions:       {self.performance_metrics.total_predictions}",
            f"  Correct Predictions:     {self.performance_metrics.correct_predictions}",
            f"  Average Confidence:      {self.performance_metrics.average_confidence:.4f}",
            f"  Average Prediction Time: {self.performance_metrics.average_prediction_time_ms:.2f}ms",
            "",
            "Per-Class Metrics:",
            "-" * 60,
        ]

        # Add per-class metrics table
        report_lines.extend(
            [
                f"{'Class':<30} {'Precision':<10} {'Recall':<10} {'F1-Score':<10} {'Support':<10}",
                "-" * 70,
            ]
        )

        for error_type, metrics in classification_metrics.per_class_metrics.items():
            class_name = error_type.value
            precision = metrics["precision"]
            recall = metrics["recall"]
            f1_score = metrics["f1_score"]
            support = int(metrics["support"])

            report_lines.append(
                f"{class_name:<30} {precision:<10.4f} {recall:<10.4f} {f1_score:<10.4f} {support:<10d}"
            )

        report_lines.extend(
            [
                "",
                "Confusion Matrix:",
                "-" * 60,
            ]
        )

        # Add confusion matrix
        if classification_metrics.confusion_matrix:
            matrix = classification_metrics.confusion_matrix.get_matrix_array()
            classes = [
                cls.value for cls in classification_metrics.confusion_matrix.classes
            ]
        else:
            matrix = np.array([])
            classes = []

        # Header
        header = "Predicted:".ljust(20)
        for cls in classes:
            header += f"{cls[:8]:<10}"
        report_lines.append(header)
        report_lines.append("-" * (20 + len(classes) * 10))

        # Matrix rows
        for i, true_cls in enumerate(classes):
            row = f"True: {true_cls[:12]:<12}"
            for j in range(len(classes)):
                row += f"{matrix[i, j]:<10d}"
            report_lines.append(row)

        return "\n".join(report_lines)

    def export_metrics(self, algorithm_name: str) -> MetricsSummary:
        """Export metrics as a structured summary."""
        classification_metrics = self.calculate_classification_metrics()

        return MetricsSummary(
            timestamp=time.time(),
            classification_metrics=classification_metrics,
            performance_metrics=self.performance_metrics,
            algorithm_name=algorithm_name,
            metadata={
                "collector_name": self.name,
                "collection_start_time": self.start_time,
                "collection_duration_s": time.time() - self.start_time,
                "num_predictions": len(self.prediction_history),
            },
        )

    def reset_metrics(self) -> None:
        """Reset all collected metrics."""
        self.confusion_matrix = ConfusionMatrix()
        self.performance_metrics = PerformanceMetrics()
        self.prediction_history.clear()
        self.start_time = time.time()
        self.logger.info(f"Reset metrics for collector: {self.name}")

    def get_top_errors(self, n: int = 5) -> List[Tuple[ErrorType, ErrorType, int]]:
        """Get the top N most common classification errors."""
        error_counts = defaultdict(int)

        for true_label, pred_label, _, _ in self.prediction_history:
            if true_label != pred_label:
                error_counts[(true_label, pred_label)] += 1

        # Sort by count (descending)
        sorted_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)

        return [
            (true_label, pred_label, count)
            for (true_label, pred_label), count in sorted_errors[:n]
        ]

    def get_confidence_statistics(self) -> Dict[str, float]:
        """Get overall confidence statistics."""
        if not self.prediction_history:
            return {}

        confidences = [conf for _, _, conf, _ in self.prediction_history]

        return {
            "mean": float(np.mean(confidences)),
            "std": float(np.std(confidences)),
            "min": float(np.min(confidences)),
            "max": float(np.max(confidences)),
            "median": float(np.median(confidences)),
            "q25": float(np.percentile(confidences, 25)),
            "q75": float(np.percentile(confidences, 75)),
        }

    def get_timing_statistics(self) -> Dict[str, float]:
        """Get timing statistics."""
        if not self.prediction_history:
            return {}

        times = [time_ms for _, _, _, time_ms in self.prediction_history]

        return {
            "mean_ms": float(np.mean(times)),
            "std_ms": float(np.std(times)),
            "min_ms": float(np.min(times)),
            "max_ms": float(np.max(times)),
            "median_ms": float(np.median(times)),
            "q25_ms": float(np.percentile(times, 25)),
            "q75_ms": float(np.percentile(times, 75)),
            "total_ms": float(np.sum(times)),
        }


class MetricsComparator:
    """Compare metrics between different classification algorithms."""

    def __init__(self) -> None:
        """Initialize the metrics comparator."""
        self.logger = logging.getLogger("MetricsComparator")
        self.metrics_summaries: Dict[str, MetricsSummary] = {}

    def add_metrics(self, algorithm_name: str, metrics_summary: MetricsSummary) -> None:
        """Add metrics for an algorithm."""
        self.metrics_summaries[algorithm_name] = metrics_summary
        self.logger.info(f"Added metrics for algorithm: {algorithm_name}")

    def compare_algorithms(self, metric: str = "f1_score") -> List[Tuple[str, float]]:
        """Compare algorithms by a specific metric."""
        results = []

        for algorithm_name, summary in self.metrics_summaries.items():
            classification_metrics = summary.classification_metrics

            if hasattr(classification_metrics, metric):
                value = getattr(classification_metrics, metric)
                results.append((algorithm_name, value))

        # Sort by metric value (descending)
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def get_best_algorithm(self, metric: str = "f1_score") -> Optional[str]:
        """Get the best performing algorithm for a specific metric."""
        comparison = self.compare_algorithms(metric)
        return comparison[0][0] if comparison else None

    def generate_comparison_report(self) -> str:
        """Generate a comparison report for all algorithms."""
        if not self.metrics_summaries:
            return "No metrics available for comparison."

        report_lines = [
            "\nAlgorithm Comparison Report",
            "=" * 50,
            "",
        ]

        # Comparison table
        metrics_to_compare = [
            "accuracy",
            "precision",
            "recall",
            "f1_score",
            "macro_f1_score",
        ]

        # Header
        header = f"{'Algorithm':<20}"
        for metric in metrics_to_compare:
            header += f"{metric.replace('_', ' ').title():<12}"
        report_lines.append(header)
        report_lines.append("-" * (20 + len(metrics_to_compare) * 12))

        # Algorithm rows
        for algorithm_name, summary in self.metrics_summaries.items():
            classification_metrics = summary.classification_metrics

            row = f"{algorithm_name:<20}"
            for metric in metrics_to_compare:
                value = getattr(classification_metrics, metric, 0.0)
                row += f"{value:<12.4f}"
            report_lines.append(row)

        # Best performers
        report_lines.extend(
            [
                "",
                "Best Performers:",
                "-" * 30,
            ]
        )

        for metric in metrics_to_compare:
            best = self.get_best_algorithm(metric)
            if best:
                best_value = getattr(
                    self.metrics_summaries[best].classification_metrics, metric, 0.0
                )
                report_lines.append(
                    f"{metric.replace('_', ' ').title():<15}: {best} ({best_value:.4f})"
                )

        return "\n".join(report_lines)


def calculate_metrics_from_predictions(
    true_labels: List[ErrorType],
    predicted_results: List[ClassificationResult],
    algorithm_name: str = "unknown",
) -> MetricsSummary:
    """Calculate metrics from lists of predictions."""
    collector = ClassificationMetricsCollector(f"batch_{algorithm_name}")

    for true_label, predicted_result in zip(
        true_labels, predicted_results, strict=True
    ):
        # Assume 1ms prediction time for batch calculations
        collector.record_prediction(true_label, predicted_result, 1.0)

    return collector.export_metrics(algorithm_name)


def compare_classifier_performance(
    true_labels: List[ErrorType],
    predictions_by_algorithm: Dict[str, List[ClassificationResult]],
) -> MetricsComparator:
    """Compare performance of multiple classifiers."""
    comparator = MetricsComparator()

    for algorithm_name, predicted_results in predictions_by_algorithm.items():
        metrics_summary = calculate_metrics_from_predictions(
            true_labels, predicted_results, algorithm_name
        )
        comparator.add_metrics(algorithm_name, metrics_summary)

    return comparator
