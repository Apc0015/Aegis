import 'package:flutter_riverpod/flutter_riverpod.dart';

/// All user-configurable settings stored locally (no API call needed).
class RapidSettings {
  final String llmProvider;
  // mainModel is the canonical name used by LLM config card
  final String mainModel;
  final String ragMode;
  final String embedProvider;
  final bool webEnabled;
  final bool forceDb;
  final bool rerankerEnabled;
  final bool llmIntent;
  final bool crossModelEval;
  final String evalModel;
  final double highConfidenceThreshold;
  final double mediumConfidenceThreshold;
  // LLM provider API key (e.g. OpenRouter)
  final String apiKey;
  // Chat mode: 'chat' | 'rag' | 'db' | 'auto'
  final String chatMode;

  const RapidSettings({
    this.llmProvider = 'openrouter',
    this.mainModel = 'meta-llama/llama-3.3-70b-instruct:free',
    this.ragMode = 'hybrid',
    this.embedProvider = 'openai',
    this.webEnabled = true,
    this.forceDb = false,
    this.rerankerEnabled = false,
    this.llmIntent = false,
    this.crossModelEval = false,
    this.evalModel = 'claude-haiku-4-5-20251001',
    this.highConfidenceThreshold = 0.7,
    this.mediumConfidenceThreshold = 0.4,
    this.apiKey = '',
    this.chatMode = 'chat',
  });

  RapidSettings copyWith({
    String? llmProvider,
    String? mainModel,
    String? ragMode,
    String? embedProvider,
    bool? webEnabled,
    bool? forceDb,
    bool? rerankerEnabled,
    bool? llmIntent,
    bool? crossModelEval,
    String? evalModel,
    double? highConfidenceThreshold,
    double? mediumConfidenceThreshold,
    String? apiKey,
    String? chatMode,
  }) =>
      RapidSettings(
        llmProvider: llmProvider ?? this.llmProvider,
        mainModel: mainModel ?? this.mainModel,
        ragMode: ragMode ?? this.ragMode,
        embedProvider: embedProvider ?? this.embedProvider,
        webEnabled: webEnabled ?? this.webEnabled,
        forceDb: forceDb ?? this.forceDb,
        rerankerEnabled: rerankerEnabled ?? this.rerankerEnabled,
        llmIntent: llmIntent ?? this.llmIntent,
        crossModelEval: crossModelEval ?? this.crossModelEval,
        evalModel: evalModel ?? this.evalModel,
        highConfidenceThreshold:
            highConfidenceThreshold ?? this.highConfidenceThreshold,
        mediumConfidenceThreshold:
            mediumConfidenceThreshold ?? this.mediumConfidenceThreshold,
        apiKey: apiKey ?? this.apiKey,
        chatMode: chatMode ?? this.chatMode,
      );
}

class SettingsNotifier extends StateNotifier<RapidSettings> {
  SettingsNotifier() : super(const RapidSettings());

  void setLlmProvider(String v) => state = state.copyWith(llmProvider: v);
  void setMainModel(String v) => state = state.copyWith(mainModel: v);
  void setRagMode(String v) => state = state.copyWith(ragMode: v);
  void setEmbedProvider(String v) => state = state.copyWith(embedProvider: v);
  void setWebEnabled(bool v) => state = state.copyWith(webEnabled: v);
  void setForceDb(bool v) => state = state.copyWith(forceDb: v);
  void setRerankerEnabled(bool v) => state = state.copyWith(rerankerEnabled: v);
  void setLlmIntent(bool v) => state = state.copyWith(llmIntent: v);
  void setCrossModelEval(bool v) => state = state.copyWith(crossModelEval: v);
  void setEvalModel(String v) => state = state.copyWith(evalModel: v);
  void setHighConfidenceThreshold(double v) =>
      state = state.copyWith(highConfidenceThreshold: v);
  void setMediumConfidenceThreshold(double v) =>
      state = state.copyWith(mediumConfidenceThreshold: v);
  void setApiKey(String v) => state = state.copyWith(apiKey: v);
  void setChatMode(String v) => state = state.copyWith(chatMode: v);
}

final settingsProvider =
    StateNotifierProvider<SettingsNotifier, RapidSettings>((_) => SettingsNotifier());
