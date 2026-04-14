import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/models/project_models.dart';
import 'api_provider.dart';

// ── Projects list notifier ───────────────────────────────────────────────────
class ProjectsNotifier extends StateNotifier<AsyncValue<List<ProjectInfo>>> {
  final Ref _ref;

  ProjectsNotifier(this._ref) : super(const AsyncLoading()) {
    _load();
  }

  Future<void> _load() async {
    state = const AsyncLoading();
    try {
      final projects = await _ref.read(apiDataSourceProvider).listProjects();
      state = AsyncData(projects);
    } catch (e, st) {
      state = AsyncError(e, st);
    }
  }

  Future<void> refresh() => _load();

  Future<void> createProject(String name) async {
    final api = _ref.read(apiDataSourceProvider);
    await api.createProject(name);
    await _load();
  }
}

final projectsProvider =
    StateNotifierProvider<ProjectsNotifier, AsyncValue<List<ProjectInfo>>>(
        (ref) => ProjectsNotifier(ref));

// ── Active project ───────────────────────────────────────────────────────────
class ActiveProjectNotifier extends StateNotifier<ProjectInfo?> {
  ActiveProjectNotifier() : super(null);

  void setActive(ProjectInfo project) => state = project;
  void clear() => state = null;
}

final activeProjectProvider =
    StateNotifierProvider<ActiveProjectNotifier, ProjectInfo?>(
        (ref) => ActiveProjectNotifier());
