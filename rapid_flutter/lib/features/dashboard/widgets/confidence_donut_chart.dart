import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_sizes.dart';
import '../../../core/constants/app_text_styles.dart';

class ConfidenceDonutChart extends StatefulWidget {
  final int high;
  final int medium;
  final int low;

  const ConfidenceDonutChart({
    super.key,
    required this.high,
    required this.medium,
    required this.low,
  });

  @override
  State<ConfidenceDonutChart> createState() => _ConfidenceDonutChartState();
}

class _ConfidenceDonutChartState extends State<ConfidenceDonutChart> {
  int? _touched;

  @override
  Widget build(BuildContext context) {
    final total = widget.high + widget.medium + widget.low;

    return Container(
      padding: const EdgeInsets.all(AppSizes.paddingLG),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppSizes.radiusLG),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.donut_large_outlined,
                  size: 16, color: AppColors.textSecondary),
              const SizedBox(width: 8),
              Text('Confidence Distribution',
                  style: AppTextStyles.headlineSmall),
            ],
          ),
          const SizedBox(height: 16),
          if (total == 0)
            SizedBox(
              height: 140,
              child: Center(
                child: Text('No queries yet',
                    style: AppTextStyles.bodySmall),
              ),
            )
          else
            SizedBox(
              height: 140,
              child: Row(
                children: [
                  Expanded(
                    flex: 3,
                    child: PieChart(
                      PieChartData(
                        pieTouchData: PieTouchData(
                          touchCallback: (event, response) {
                            setState(() {
                              if (!event.isInterestedForInteractions ||
                                  response == null ||
                                  response.touchedSection == null) {
                                _touched = null;
                                return;
                              }
                              _touched = response
                                  .touchedSection!.touchedSectionIndex;
                            });
                          },
                        ),
                        sections: _buildSections(total),
                        centerSpaceRadius: 40,
                        sectionsSpace: 2,
                      ),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    flex: 2,
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _LegendItem(
                          color: AppColors.highConf,
                          label: 'High',
                          count: widget.high,
                          total: total,
                        ),
                        const SizedBox(height: 8),
                        _LegendItem(
                          color: AppColors.mediumConf,
                          label: 'Medium',
                          count: widget.medium,
                          total: total,
                        ),
                        const SizedBox(height: 8),
                        _LegendItem(
                          color: AppColors.lowConf,
                          label: 'Low',
                          count: widget.low,
                          total: total,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  List<PieChartSectionData> _buildSections(int total) {
    final data = [
      (widget.high, AppColors.highConf, 'High'),
      (widget.medium, AppColors.mediumConf, 'Med'),
      (widget.low, AppColors.lowConf, 'Low'),
    ];

    return List.generate(data.length, (i) {
      final (count, color, label) = data[i];
      final isTouched = _touched == i;
      final pct = total > 0 ? (count / total * 100).toStringAsFixed(0) : '0';
      return PieChartSectionData(
        color: color,
        value: count.toDouble(),
        title: isTouched ? '$pct%' : '',
        radius: isTouched ? 36 : 30,
        titleStyle: AppTextStyles.labelSmall.copyWith(color: Colors.white),
      );
    });
  }
}

class _LegendItem extends StatelessWidget {
  final Color color;
  final String label;
  final int count;
  final int total;

  const _LegendItem({
    required this.color,
    required this.label,
    required this.count,
    required this.total,
  });

  @override
  Widget build(BuildContext context) {
    final pct = total > 0 ? (count / total * 100).toStringAsFixed(0) : '0';
    return Row(
      children: [
        Container(
          width: 8, height: 8,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 6),
        Text(label, style: AppTextStyles.bodySmall),
        const Spacer(),
        Text('$pct%',
            style: AppTextStyles.labelSmall
                .copyWith(color: AppColors.textSecondary)),
      ],
    );
  }
}
