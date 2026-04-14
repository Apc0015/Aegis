import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_sizes.dart';
import '../../../core/constants/app_text_styles.dart';

class AuditFilters {
  final String searchQuery;
  final String? verdictFilter;
  final String? roleFilter;

  const AuditFilters({
    this.searchQuery = '',
    this.verdictFilter,
    this.roleFilter,
  });

  AuditFilters copyWith({
    String? searchQuery,
    String? verdictFilter,
    String? roleFilter,
    bool clearVerdict = false,
    bool clearRole = false,
  }) =>
      AuditFilters(
        searchQuery: searchQuery ?? this.searchQuery,
        verdictFilter:
            clearVerdict ? null : (verdictFilter ?? this.verdictFilter),
        roleFilter: clearRole ? null : (roleFilter ?? this.roleFilter),
      );
}

class AuditFilterBar extends StatelessWidget {
  final AuditFilters filters;
  final ValueChanged<AuditFilters> onChanged;

  const AuditFilterBar({
    super.key,
    required this.filters,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        // Search
        SizedBox(
          width: 220,
          height: 36,
          child: TextField(
            decoration: InputDecoration(
              hintText: 'Search queries…',
              prefixIcon: const Icon(Icons.search, size: 16),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(AppSizes.radiusFull),
                borderSide: const BorderSide(color: AppColors.border),
              ),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 0),
              isDense: true,
            ),
            style: AppTextStyles.bodySmall,
            onChanged: (v) =>
                onChanged(filters.copyWith(searchQuery: v)),
          ),
        ),

        // Verdict filter
        _FilterChip(
          label: 'All',
          selected: filters.verdictFilter == null,
          onSelected: (_) => onChanged(filters.copyWith(clearVerdict: true)),
        ),
        _FilterChip(
          label: 'High',
          selected: filters.verdictFilter == 'high',
          color: AppColors.highConf,
          onSelected: (_) =>
              onChanged(filters.copyWith(verdictFilter: 'high')),
        ),
        _FilterChip(
          label: 'Medium',
          selected: filters.verdictFilter == 'medium',
          color: AppColors.mediumConf,
          onSelected: (_) =>
              onChanged(filters.copyWith(verdictFilter: 'medium')),
        ),
        _FilterChip(
          label: 'Low',
          selected: filters.verdictFilter == 'low',
          color: AppColors.lowConf,
          onSelected: (_) =>
              onChanged(filters.copyWith(verdictFilter: 'low')),
        ),
      ],
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final Color? color;
  final ValueChanged<bool> onSelected;

  const _FilterChip({
    required this.label,
    required this.selected,
    required this.onSelected,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    final activeColor = color ?? AppColors.primary;
    return GestureDetector(
      onTap: () => onSelected(!selected),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 120),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: selected ? activeColor.withOpacity(0.1) : AppColors.surface,
          borderRadius: BorderRadius.circular(AppSizes.radiusFull),
          border: Border.all(
            color: selected ? activeColor : AppColors.border,
          ),
        ),
        child: Text(
          label,
          style: AppTextStyles.labelSmall.copyWith(
            color: selected ? activeColor : AppColors.textSecondary,
          ),
        ),
      ),
    );
  }
}
