import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/models/audit_models.dart';
import 'api_provider.dart';

// ── Audit notifier ───────────────────────────────────────────────────────────
class AuditNotifier extends StateNotifier<AsyncValue<List<AuditRecord>>> {
  final Ref _ref;

  AuditNotifier(this._ref) : super(const AsyncLoading()) {
    _load();
  }

  Future<void> _load() async {
    state = const AsyncLoading();
    try {
      final records =
          await _ref.read(apiDataSourceProvider).getAuditLog(limit: 200);
      state = AsyncData(records);
    } catch (e, st) {
      state = AsyncError(e, st);
    }
  }

  Future<void> refresh() => _load();

  Future<void> exportCsv() async {
    await _ref.read(apiDataSourceProvider).exportAuditCsv();
  }
}

final auditProvider =
    StateNotifierProvider<AuditNotifier, AsyncValue<List<AuditRecord>>>(
        (ref) => AuditNotifier(ref));
