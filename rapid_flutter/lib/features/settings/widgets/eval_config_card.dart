import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_sizes.dart';
import '../../../core/constants/app_text_styles.dart';
import '../../../providers/settings_provider.dart';

class EvalConfigCard extends ConsumerWidget {
  const EvalConfigCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(settingsProvider);
    final notifier = ref.read(settingsProvider.notifier);

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
              const Icon(Icons.compare_arrows_rounded,
                  size: 16, color: AppColors.textSecondary),
              const SizedBox(width: 8),
              Text('Evaluation', style: AppTextStyles.headlineSmall),
            ],
          ),
          const SizedBox(height: 16),

          // Cross-model eval toggle
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Cross-model evaluation',
                        style: AppTextStyles.bodySmall
                            .copyWith(color: AppColors.textPrimary)),
                    const SizedBox(height: 2),
                    Text(
                      'Use a second LLM to verify the primary answer',
                      style: AppTextStyles.caption,
                    ),
                  ],
                ),
              ),
              Switch(
                value: settings.crossModelEval,
                onChanged: (v) => notifier.setCrossModelEval(v),
                activeColor: AppColors.primary,
              ),
            ],
          ),

          if (settings.crossModelEval) ...[
            const Divider(height: 24),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Evaluator model', style: AppTextStyles.caption),
                const SizedBox(height: 6),
                DropdownButtonFormField<String>(
                  value: settings.evalModel.isNotEmpty
                      ? settings.evalModel
                      : 'claude-haiku-4-5-20251001',
                  decoration: const InputDecoration(isDense: true),
                  items: const [
                    DropdownMenuItem(
                      value: 'claude-haiku-4-5-20251001',
                      child: Text('claude-haiku-4-5-20251001'),
                    ),
                    DropdownMenuItem(
                      value: 'gpt-4o-mini',
                      child: Text('gpt-4o-mini'),
                    ),
                    DropdownMenuItem(
                      value: 'gemini-1.5-flash',
                      child: Text('gemini-1.5-flash'),
                    ),
                  ],
                  onChanged: (v) {
                    if (v != null) notifier.setEvalModel(v);
                  },
                ),
              ],
            ),
          ],

          const Divider(height: 24),

          // Confidence thresholds
          Text('Confidence thresholds',
              style: AppTextStyles.bodySmall
                  .copyWith(color: AppColors.textPrimary)),
          const SizedBox(height: 12),
          _ThresholdSlider(
            label: 'High ≥',
            value: settings.highConfidenceThreshold,
            color: AppColors.highConf,
            onChanged: (v) => notifier.setHighConfidenceThreshold(v),
          ),
          const SizedBox(height: 8),
          _ThresholdSlider(
            label: 'Medium ≥',
            value: settings.mediumConfidenceThreshold,
            color: AppColors.mediumConf,
            onChanged: (v) => notifier.setMediumConfidenceThreshold(v),
          ),
        ],
      ),
    );
  }
}

class _ThresholdSlider extends StatelessWidget {
  final String label;
  final double value;
  final Color color;
  final ValueChanged<double> onChanged;

  const _ThresholdSlider({
    required this.label,
    required this.value,
    required this.color,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(
          width: 80,
          child: Text(
            '$label ${(value * 100).toStringAsFixed(0)}%',
            style: AppTextStyles.caption.copyWith(color: color),
          ),
        ),
        Expanded(
          child: SliderTheme(
            data: SliderTheme.of(context).copyWith(
              activeTrackColor: color,
              thumbColor: color,
              overlayColor: color.withOpacity(0.1),
              inactiveTrackColor: AppColors.border,
              trackHeight: 3,
              thumbShape:
                  const RoundSliderThumbShape(enabledThumbRadius: 7),
            ),
            child: Slider(
              value: value,
              min: 0.0,
              max: 1.0,
              divisions: 20,
              onChanged: onChanged,
            ),
          ),
        ),
      ],
    );
  }
}
