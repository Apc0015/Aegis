import 'package:data_table_2/data_table_2.dart';
import 'package:flutter/material.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_text_styles.dart';
import '../../../data/models/audit_models.dart';
import 'audit_filter_bar.dart';

class AuditTable extends StatefulWidget {
  final List<AuditRecord> records;

  const AuditTable({super.key, required this.records});

  @override
  State<AuditTable> createState() => _AuditTableState();
}

class _AuditTableState extends State<AuditTable> {
  AuditFilters _filters = const AuditFilters();
  int _rowsPerPage = 20;

  List<AuditRecord> get _filtered {
    var list = widget.records;
    if (_filters.searchQuery.isNotEmpty) {
      final q = _filters.searchQuery.toLowerCase();
      list = list
          .where((r) =>
              r.query.toLowerCase().contains(q) ||
              r.userId.toLowerCase().contains(q) ||
              (r.projectId ?? '').toLowerCase().contains(q))
          .toList();
    }
    if (_filters.verdictFilter != null) {
      list = list
          .where((r) =>
              r.verdict?.toLowerCase() == _filters.verdictFilter)
          .toList();
    }
    return list;
  }

  @override
  Widget build(BuildContext context) {
    final filtered = _filtered;

    return Column(
      children: [
        AuditFilterBar(
          filters: _filters,
          onChanged: (f) => setState(() => _filters = f),
        ),
        const SizedBox(height: 16),
        Container(
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.border),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: SizedBox(
              height: 500,
              child: DataTable2(
                columnSpacing: 16,
                horizontalMargin: 16,
                headingRowHeight: 40,
                dataRowHeight: 52,
                headingTextStyle: AppTextStyles.labelSmall
                    .copyWith(color: AppColors.textSecondary),
                dataTextStyle: AppTextStyles.bodySmall,
                headingRowColor: WidgetStateProperty.all(AppColors.surfaceVariant),
                columns: const [
                  DataColumn2(label: Text('Query'), size: ColumnSize.L),
                  DataColumn2(
                      label: Text('User'), size: ColumnSize.S),
                  DataColumn2(
                      label: Text('Project'), size: ColumnSize.S),
                  DataColumn2(
                      label: Text('Verdict'), size: ColumnSize.S),
                  DataColumn2(
                      label: Text('Conf.'), size: ColumnSize.S,
                      numeric: true),
                  DataColumn2(
                      label: Text('Route'), size: ColumnSize.S),
                  DataColumn2(
                      label: Text('Latency'), size: ColumnSize.S,
                      numeric: true),
                ],
                rows: filtered
                    .map((r) => DataRow2(
                          cells: [
                            DataCell(Text(
                              r.query.length > 80
                                  ? '${r.query.substring(0, 80)}…'
                                  : r.query,
                              overflow: TextOverflow.ellipsis,
                            )),
                            DataCell(Text(r.userId)),
                            DataCell(Text(r.projectId ?? '—')),
                            DataCell(_VerdictChip(verdict: r.verdict)),
                            DataCell(Text(
                              r.confidence != null
                                  ? '${(r.confidence! * 100).toStringAsFixed(0)}%'
                                  : '—',
                            )),
                            DataCell(Text(r.routingPath ?? '—')),
                            DataCell(Text(
                              r.latencyMs != null ? '${r.latencyMs}ms' : '—',
                            )),
                          ],
                        ))
                    .toList(),
                empty: Center(
                  child: Text('No records match filters',
                      style: AppTextStyles.bodySmall),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          '${filtered.length} record${filtered.length != 1 ? 's' : ''}',
          style: AppTextStyles.caption,
        ),
      ],
    );
  }
}

class _VerdictChip extends StatelessWidget {
  final String? verdict;
  const _VerdictChip({this.verdict});

  @override
  Widget build(BuildContext context) {
    Color color;
    Color bg;
    switch (verdict?.toLowerCase()) {
      case 'high':
        color = AppColors.highConf;
        bg = AppColors.highConfBg;
        break;
      case 'medium':
        color = AppColors.mediumConf;
        bg = AppColors.mediumConfBg;
        break;
      case 'low':
        color = AppColors.lowConf;
        bg = AppColors.lowConfBg;
        break;
      default:
        color = AppColors.textMuted;
        bg = AppColors.surfaceVariant;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        verdict?.toUpperCase() ?? '—',
        style: AppTextStyles.labelSmall.copyWith(color: color),
      ),
    );
  }
}
