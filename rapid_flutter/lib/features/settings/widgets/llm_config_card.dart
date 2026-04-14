import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_sizes.dart';
import '../../../core/constants/app_text_styles.dart';
import '../../../providers/settings_provider.dart';
import '../../../providers/models_provider.dart';

const _fallbackModels = <String, List<String>>{
  'openrouter': [
    'meta-llama/llama-3.1-8b-instruct:free',
    'google/gemma-2-9b-it:free',
    'mistralai/mistral-7b-instruct:free',
  ],
  'ollama': [
    'llama3.2',
    'llama3.1',
    'mistral',
  ],
};

class LlmConfigCard extends ConsumerStatefulWidget {
  const LlmConfigCard({super.key});

  @override
  ConsumerState<LlmConfigCard> createState() => _LlmConfigCardState();
}

class _LlmConfigCardState extends ConsumerState<LlmConfigCard> {
  late TextEditingController _apiKeyCtrl;
  // Bump this to force a provider refresh when user clicks Refresh
  int _refreshKey = 0;

  @override
  void initState() {
    super.initState();
    _apiKeyCtrl = TextEditingController(
      text: ref.read(settingsProvider).apiKey,
    );
  }

  @override
  void dispose() {
    _apiKeyCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final settings = ref.watch(settingsProvider);
    final notifier = ref.read(settingsProvider.notifier);

    const providers = ['openrouter', 'ollama'];

    // Watch the models async value — keyed by (provider, apiKey, refreshKey)
    // We encode refreshKey into the apiKey string so FutureProvider.family re-fires
    final providerKey = settings.llmProvider;
    final apiKeyForFetch =
        providerKey == 'openrouter' ? settings.apiKey : '';
    final fetchKey = '$apiKeyForFetch#$_refreshKey';
    final modelsAsync = ref.watch(modelsProvider((providerKey, fetchKey)));

    return _Card(
      title: 'LLM Provider',
      icon: Icons.smart_toy_outlined,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Provider dropdown ───────────────────────────────────────────
          Text('Provider', style: AppTextStyles.caption),
          const SizedBox(height: 4),
          DropdownButtonFormField<String>(
            value: providers.contains(settings.llmProvider)
                ? settings.llmProvider
                : providers.first,
            decoration: const InputDecoration(isDense: true),
            items: providers
                .map((p) => DropdownMenuItem(
                    value: p,
                    child: Text(
                      p == 'openrouter' ? 'OpenRouter' : 'Ollama (local)',
                      style: AppTextStyles.bodySmall,
                    )))
                .toList(),
            onChanged: (v) {
              if (v != null) {
                notifier.setLlmProvider(v);
                // Reset model to fallback when switching provider
                final fallback = _fallbackModels[v]?.first ?? '';
                if (fallback.isNotEmpty) notifier.setMainModel(fallback);
              }
            },
          ),

          // ── API key field (OpenRouter only) ─────────────────────────────
          if (settings.llmProvider == 'openrouter') ...[
            const SizedBox(height: 16),
            Text('API Key', style: AppTextStyles.caption),
            const SizedBox(height: 4),
            TextField(
              controller: _apiKeyCtrl,
              obscureText: true,
              decoration: InputDecoration(
                hintText: 'sk-or-...',
                isDense: true,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(AppSizes.radiusMD),
                ),
                suffixIcon: IconButton(
                  icon: const Icon(Icons.check_rounded, size: 16),
                  tooltip: 'Save key',
                  onPressed: () {
                    notifier.setApiKey(_apiKeyCtrl.text.trim());
                    setState(() => _refreshKey++);
                  },
                ),
              ),
              onSubmitted: (v) {
                notifier.setApiKey(v.trim());
                setState(() => _refreshKey++);
              },
            ),
          ],

          // ── Model dropdown ──────────────────────────────────────────────
          const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Model', style: AppTextStyles.caption),
                    const SizedBox(height: 4),
                    modelsAsync.when(
                      loading: () => DropdownButtonFormField<String>(
                        value: null,
                        decoration: const InputDecoration(
                          isDense: true,
                          hintText: 'Fetching models…',
                        ),
                        items: const [],
                        onChanged: null,
                      ),
                      error: (_, __) => _ModelDropdown(
                        models: _fallbackModels[settings.llmProvider] ?? [],
                        selected: settings.mainModel,
                        onChanged: notifier.setMainModel,
                      ),
                      data: (models) {
                        final ids =
                            models.map((m) => m['id'] ?? '').where((id) => id.isNotEmpty).toList();
                        if (ids.isEmpty) {
                          // Fallback if API returned empty list
                          return _ModelDropdown(
                            models: _fallbackModels[settings.llmProvider] ?? [],
                            selected: settings.mainModel,
                            onChanged: notifier.setMainModel,
                          );
                        }
                        return _ModelDropdown(
                          models: ids,
                          selected: ids.contains(settings.mainModel)
                              ? settings.mainModel
                              : ids.first,
                          onChanged: notifier.setMainModel,
                        );
                      },
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Tooltip(
                message: 'Refresh model list',
                child: IconButton(
                  icon: const Icon(Icons.refresh_rounded, size: 18),
                  onPressed: () => setState(() => _refreshKey++),
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ModelDropdown extends StatelessWidget {
  final List<String> models;
  final String selected;
  final ValueChanged<String> onChanged;

  const _ModelDropdown({
    required this.models,
    required this.selected,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final safeSelected = models.contains(selected) ? selected : models.first;
    return DropdownButtonFormField<String>(
      value: safeSelected,
      isExpanded: true,
      decoration: const InputDecoration(isDense: true),
      items: models
          .map((m) => DropdownMenuItem(
              value: m,
              child: Text(
                m,
                style: AppTextStyles.bodySmall,
                overflow: TextOverflow.ellipsis,
              )))
          .toList(),
      onChanged: (v) {
        if (v != null) onChanged(v);
      },
    );
  }
}

class _Card extends StatelessWidget {
  final String title;
  final IconData icon;
  final Widget child;

  const _Card({
    required this.title,
    required this.icon,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
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
              Icon(icon, size: 16, color: AppColors.textSecondary),
              const SizedBox(width: 8),
              Text(title, style: AppTextStyles.headlineSmall),
            ],
          ),
          const SizedBox(height: 16),
          child,
        ],
      ),
    );
  }
}
