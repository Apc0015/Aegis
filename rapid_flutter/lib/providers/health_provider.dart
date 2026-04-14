import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/models/health_models.dart';
import 'api_provider.dart';

/// Health status — auto-refreshed on watch, no polling needed (use ref.refresh)
final healthProvider = FutureProvider<HealthStatus>((ref) async {
  return ref.watch(apiDataSourceProvider).getHealth();
});
