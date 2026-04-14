import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import '../data/models/query_models.dart';
import '../core/network/sse_client.dart';
import 'api_provider.dart';
import 'settings_provider.dart';

const _uuid = Uuid();

class ChatState {
  final List<ChatMessage> messages;
  final bool isStreaming;
  final String? error;

  const ChatState({
    this.messages = const [],
    this.isStreaming = false,
    this.error,
  });

  ChatState copyWith({
    List<ChatMessage>? messages,
    bool? isStreaming,
    String? error,
    bool clearError = false,
  }) =>
      ChatState(
        messages: messages ?? this.messages,
        isStreaming: isStreaming ?? this.isStreaming,
        error: clearError ? null : (error ?? this.error),
      );
}

class ChatNotifier extends StateNotifier<ChatState> {
  final Ref _ref;
  final String projectId;

  ChatNotifier(this._ref, this.projectId) : super(const ChatState());

  Future<void> sendMessage(String userQuery) async {
    if (userQuery.trim().isEmpty || state.isStreaming) return;

    final settings = _ref.read(settingsProvider);
    final chatMode = settings.chatMode;
    // When in chat mode, project_id is not needed — use 'general' as fallback
    final effectiveProjectId =
        projectId.isNotEmpty ? projectId : (chatMode == 'chat' ? 'general' : '');

    // 1. Append user message
    final userMsg = ChatMessage(
      id: _uuid.v4(),
      role: MessageRole.user,
      content: userQuery.trim(),
      timestamp: DateTime.now(),
    );

    // 2. Append partial assistant placeholder
    final assistantId = _uuid.v4();
    final partialMsg = ChatMessage(
      id: assistantId,
      role: MessageRole.assistant,
      content: '',
      timestamp: DateTime.now(),
      isPartial: true,
    );

    state = state.copyWith(
      messages: [...state.messages, userMsg, partialMsg],
      isStreaming: true,
      clearError: true,
    );

    // 3. Subscribe to SSE stream
    final api = _ref.read(apiDataSourceProvider);
    final buffer = StringBuffer();

    try {
      await for (final event in api.queryStream(
        userQuery: userQuery.trim(),
        projectId: effectiveProjectId,
        ragMode: settings.ragMode,
        mode: chatMode,
        forceDb: settings.forceDb,
        llmIntent: settings.llmIntent,
      )) {
        switch (event) {
          case SseToken(:final token):
            buffer.write(token);
            _updateLastMessage((msg) => msg.copyWith(content: buffer.toString()));

          case SseResult(:final data):
            final result = QueryResult.fromJson(data);
            _updateLastMessage((msg) => msg.copyWith(
              content: result.answer,
              result: result,
              isPartial: false,
            ));

          case SseDone():
            // Final sentinel — streaming complete
            _finalizeStreaming();

          case SseError(:final message):
            _updateLastMessage((msg) => msg.copyWith(
              content: 'Error: $message',
              isPartial: false,
            ));
            state = state.copyWith(isStreaming: false, error: message);
            return;
        }
      }
    } catch (e) {
      _updateLastMessage((msg) => msg.copyWith(
        content: 'Connection error: $e',
        isPartial: false,
      ));
      state = state.copyWith(isStreaming: false, error: e.toString());
      return;
    }

    _finalizeStreaming();
  }

  void _updateLastMessage(ChatMessage Function(ChatMessage) update) {
    final msgs = List<ChatMessage>.from(state.messages);
    if (msgs.isEmpty) return;
    msgs[msgs.length - 1] = update(msgs.last);
    state = state.copyWith(messages: msgs);
  }

  void _finalizeStreaming() {
    // Ensure last message is no longer partial
    final msgs = List<ChatMessage>.from(state.messages);
    if (msgs.isNotEmpty && msgs.last.isPartial) {
      msgs[msgs.length - 1] = msgs.last.copyWith(isPartial: false);
    }
    state = state.copyWith(messages: msgs, isStreaming: false);
  }

  void clearHistory() {
    state = const ChatState();
  }
}

// Family provider — one notifier per projectId
final chatProvider = StateNotifierProvider.family<ChatNotifier, ChatState, String>(
  (ref, projectId) => ChatNotifier(ref, projectId),
);
