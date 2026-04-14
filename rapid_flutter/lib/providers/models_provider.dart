import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'api_provider.dart';

/// FutureProvider.family that fetches available models from the backend.
///
/// Usage:
///   ref.watch(modelsProvider(('openrouter', apiKey)))
///   ref.watch(modelsProvider(('ollama', '')))
///
/// Returns List<Map<String,String>> with 'id' and 'name' keys.
final modelsProvider = FutureProvider.family<List<Map<String, String>>, (String, String)>(
  (ref, params) async {
    final (provider, apiKey) = params;
    final api = ref.read(apiDataSourceProvider);
    return api.listModels(provider: provider, apiKey: apiKey);
  },
);
