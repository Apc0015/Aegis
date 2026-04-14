import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_sizes.dart';
import '../../core/constants/app_text_styles.dart';
import '../../data/models/query_models.dart';
import '../../providers/chat_provider.dart';
import '../../providers/project_provider.dart';
import '../../providers/settings_provider.dart';
import '../../shared/widgets/error_banner.dart';
import 'widgets/assistant_message_bubble.dart';
import 'widgets/streaming_bubble.dart';

class ChatScreen extends ConsumerStatefulWidget {
  final String? initialProjectId;
  const ChatScreen({super.key, this.initialProjectId});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _inputCtrl = TextEditingController();
  final _scrollCtrl = ScrollController();
  late String _projectId;

  @override
  void initState() {
    super.initState();
    _projectId = widget.initialProjectId ?? '';
    if (widget.initialProjectId != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        // Optionally set active project
      });
    }
  }

  @override
  void dispose() {
    _inputCtrl.dispose();
    _scrollCtrl.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollCtrl.hasClients) {
        _scrollCtrl.animateTo(
          _scrollCtrl.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _send() async {
    final q = _inputCtrl.text.trim();
    final settings = ref.read(settingsProvider);
    // Allow sending without a project in chat mode
    if (q.isEmpty) return;
    if (_projectId.isEmpty && settings.chatMode != 'chat') return;
    _inputCtrl.clear();
    final effectiveId = _projectId.isNotEmpty ? _projectId : 'general';
    await ref.read(chatProvider(effectiveId).notifier).sendMessage(q);
    _scrollToBottom();
  }

  @override
  Widget build(BuildContext context) {
    final settings = ref.watch(settingsProvider);
    final chatMode = settings.chatMode;

    // In chat mode, allow chatting without a project
    final activeProject = ref.watch(activeProjectProvider);
    if (_projectId.isEmpty && activeProject != null) {
      _projectId = activeProject.projectId;
    }

    final effectiveId = _projectId.isNotEmpty ? _projectId : 'general';
    final chatState = ref.watch(chatProvider(effectiveId));

    // Whether we can show the chat UI (either in chat mode OR a project is selected)
    final canChat = chatMode == 'chat' || _projectId.isNotEmpty;

    return Column(
      children: [
        // ── No project selected, not in chat mode ──────────────────────────────
        if (!canChat)
          Expanded(child: _WelcomeState())
        else ...[
          // ── Chat messages ──────────────────────────────────────────────────
          Expanded(
            child: chatState.messages.isEmpty
                ? _EmptyState(chatMode: chatMode, projectId: _projectId)
                : _MessageList(
                    messages: chatState.messages,
                    isStreaming: chatState.isStreaming,
                    scrollCtrl: _scrollCtrl,
                  ),
          ),

          // ── Error ──────────────────────────────────────────────────────────
          if (chatState.error != null)
            ErrorBanner(message: chatState.error!),

          // ── Mode bar (above input) ─────────────────────────────────────────
          _ModeBar(
            chatMode: chatMode,
            onModeChanged: (mode) =>
                ref.read(settingsProvider.notifier).setChatMode(mode),
          ),

          // ── Input bar ──────────────────────────────────────────────────────
          _InputBar(
            controller: _inputCtrl,
            isStreaming: chatState.isStreaming,
            hasMessages: chatState.messages.isNotEmpty,
            chatMode: chatMode,
            onSend: _send,
            onClear: () =>
                ref.read(chatProvider(effectiveId).notifier).clearHistory(),
          ),
        ],
      ],
    );
  }
}

// ── Welcome state (no project selected) ─────────────────────────────────────
class _WelcomeState extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSizes.paddingXL),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 680),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              const SizedBox(height: 40),
              Container(
                padding: const EdgeInsets.all(AppSizes.paddingXXL),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFFEEF2FF), Color(0xFFF5F3FF)],
                    begin: Alignment.topLeft, end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(AppSizes.radiusXL),
                  border: Border.all(color: AppColors.primaryBorder),
                ),
                child: Column(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: AppColors.primary,
                        borderRadius:
                            BorderRadius.circular(AppSizes.radiusMD),
                      ),
                      child: const Icon(Icons.psychology_outlined,
                          color: Colors.white, size: 28),
                    ),
                    const SizedBox(height: 20),
                    Text('RAPID Intelligence',
                        style: AppTextStyles.displaySmall,
                        textAlign: TextAlign.center),
                    const SizedBox(height: 8),
                    Text(
                      'Select or create a project to start querying your documents',
                      style: AppTextStyles.bodySmall,
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 28),
                    OutlinedButton.icon(
                      onPressed: () => context.go('/projects'),
                      icon: const Icon(Icons.folder_outlined, size: 16),
                      label: const Text('Go to Projects'),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 36),
              // Feature cards
              _FeatureGrid(),
            ],
          ),
        ),
      ),
    ).animate().fadeIn(duration: 300.ms);
  }
}

class _FeatureGrid extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    const features = [
      (Icons.lock_outline_rounded, 'Privacy Firewall',
          'LLM never sees raw data — all content is summarized before generation'),
      (Icons.shield_outlined, 'Role-Based Access',
          'Column-level RBAC enforced before any data reaches the model'),
      (Icons.bar_chart_rounded, 'Confidence Scoring',
          '3-axis scoring: relevance, faithfulness, and completeness'),
      (Icons.manage_search_rounded, 'Hybrid Retrieval',
          'Vector + BM25 with Reciprocal Rank Fusion and optional cross-encoder reranking'),
    ];

    return GridView.count(
      crossAxisCount: 2, shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisSpacing: 12, mainAxisSpacing: 12,
      childAspectRatio: 1.8,
      children: features
          .map((f) => Container(
                padding: const EdgeInsets.all(AppSizes.paddingMD),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius:
                      BorderRadius.circular(AppSizes.radiusLG),
                  border: Border.all(color: AppColors.border),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(f.$1, size: 18, color: AppColors.primary),
                    const SizedBox(height: 6),
                    Text(f.$2, style: AppTextStyles.headlineSmall),
                    const SizedBox(height: 2),
                    Text(f.$3,
                        style: AppTextStyles.caption, maxLines: 2,
                        overflow: TextOverflow.ellipsis),
                  ],
                ),
              ))
          .toList(),
    );
  }
}

// ── Empty state (project selected or chat mode, no messages yet) ─────────────
class _EmptyState extends StatelessWidget {
  final String chatMode;
  final String projectId;
  const _EmptyState({required this.chatMode, required this.projectId});

  @override
  Widget build(BuildContext context) {
    final isChatMode = chatMode == 'chat';
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.chat_bubble_outline_rounded,
              size: 48, color: AppColors.textMuted),
          const SizedBox(height: 16),
          Text(
            isChatMode ? 'Ask me anything' : 'Ask anything about your documents',
            style: AppTextStyles.headlineMedium,
          ),
          const SizedBox(height: 6),
          if (!isChatMode && projectId.isNotEmpty)
            Text('Project: $projectId', style: AppTextStyles.bodySmall),
          if (isChatMode)
            Text('Using direct LLM — no retrieval', style: AppTextStyles.bodySmall),
        ],
      ),
    );
  }
}

// ── Message list ─────────────────────────────────────────────────────────────
class _MessageList extends StatelessWidget {
  final List<ChatMessage> messages;
  final bool isStreaming;
  final ScrollController scrollCtrl;

  const _MessageList({
    required this.messages,
    required this.isStreaming,
    required this.scrollCtrl,
  });

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      controller: scrollCtrl,
      padding: const EdgeInsets.all(AppSizes.paddingLG),
      itemCount: messages.length,
      itemBuilder: (_, i) {
        final msg = messages[i];
        if (msg.role == MessageRole.user) {
          return _UserBubble(content: msg.content);
        }
        if (msg.isPartial) {
          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const _AssistantAvatar(),
              const SizedBox(width: 10),
              Flexible(child: StreamingBubble(content: msg.content)),
            ],
          );
        }
        if (msg.result != null) {
          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const _AssistantAvatar(),
              const SizedBox(width: 10),
              Flexible(
                  child: AssistantMessageBubble(result: msg.result!)),
            ],
          );
        }
        return const SizedBox.shrink();
      },
    );
  }
}

class _UserBubble extends StatelessWidget {
  final String content;
  const _UserBubble({required this.content});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerRight,
      child: Container(
        constraints: const BoxConstraints(maxWidth: AppSizes.bubbleMaxWidth),
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.symmetric(
          horizontal: AppSizes.bubblePadH,
          vertical: AppSizes.bubblePadV,
        ),
        decoration: BoxDecoration(
          color: AppColors.userBubble,
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(AppSizes.radiusLG),
            topRight: Radius.circular(4),
            bottomLeft: Radius.circular(AppSizes.radiusLG),
            bottomRight: Radius.circular(AppSizes.radiusLG),
          ),
        ),
        child: Text(content,
            style: AppTextStyles.bodyMedium.copyWith(
                color: AppColors.userBubbleText)),
      ),
    ).animate().fadeIn(duration: 150.ms).slideX(begin: 0.03);
  }
}

class _AssistantAvatar extends StatelessWidget {
  const _AssistantAvatar();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 28, height: 28,
      decoration: BoxDecoration(
        color: AppColors.primaryLight,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppColors.primaryBorder),
      ),
      child: const Icon(Icons.psychology_outlined,
          size: 16, color: AppColors.primary),
    );
  }
}

// ── Mode bar (above input) ───────────────────────────────────────────────────
class _ModeBar extends StatelessWidget {
  final String chatMode;
  final ValueChanged<String> onModeChanged;

  const _ModeBar({
    required this.chatMode,
    required this.onModeChanged,
  });

  @override
  Widget build(BuildContext context) {
    final dbOn = chatMode == 'rag' || chatMode == 'db';

    return Container(
      color: AppColors.surface,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Row(
        children: [
          const Icon(Icons.storage_outlined, size: 14, color: AppColors.textMuted),
          const SizedBox(width: 6),
          Text('Company Database', style: AppTextStyles.caption),
          const SizedBox(width: 8),
          Switch(
            value: dbOn,
            onChanged: (on) {
              if (!on) {
                onModeChanged('chat');
              } else {
                // Default to RAG when toggling on
                onModeChanged('rag');
              }
            },
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
          ),
          if (dbOn) ...[
            const SizedBox(width: 12),
            _ModeChip(
              label: 'Documents (RAG)',
              selected: chatMode == 'rag',
              onTap: () => onModeChanged('rag'),
            ),
            const SizedBox(width: 6),
            _ModeChip(
              label: 'SQL Database',
              selected: chatMode == 'db',
              onTap: () => onModeChanged('db'),
            ),
          ],
        ],
      ),
    );
  }
}

class _ModeChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _ModeChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: selected ? AppColors.primary : AppColors.surface,
          borderRadius: BorderRadius.circular(AppSizes.radiusFull),
          border: Border.all(
            color: selected ? AppColors.primary : AppColors.border,
          ),
        ),
        child: Text(
          label,
          style: AppTextStyles.caption.copyWith(
            color: selected ? Colors.white : AppColors.textSecondary,
            fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
          ),
        ),
      ),
    );
  }
}

// ── Input bar ─────────────────────────────────────────────────────────────────
class _InputBar extends StatelessWidget {
  final TextEditingController controller;
  final bool isStreaming;
  final bool hasMessages;
  final String chatMode;
  final VoidCallback onSend;
  final VoidCallback onClear;

  const _InputBar({
    required this.controller,
    required this.isStreaming,
    required this.hasMessages,
    required this.chatMode,
    required this.onSend,
    required this.onClear,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(top: BorderSide(color: AppColors.border, width: 1)),
      ),
      padding: const EdgeInsets.symmetric(
          horizontal: AppSizes.inputBarPadH, vertical: 10),
      child: Row(
        children: [
          // Clear button
          if (hasMessages && !isStreaming)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: Tooltip(
                message: 'Clear chat',
                child: IconButton(
                  onPressed: onClear,
                  icon: const Icon(Icons.clear_all_rounded,
                      size: 20, color: AppColors.textMuted),
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                ),
              ),
            ),

          // Text field
          Expanded(
            child: TextField(
              controller: controller,
              enabled: !isStreaming,
              decoration: InputDecoration(
                hintText: isStreaming
                    ? 'Generating answer…'
                    : chatMode == 'chat'
                        ? 'Ask me anything…'
                        : 'Ask about your documents…',
                border: OutlineInputBorder(
                  borderRadius:
                      BorderRadius.circular(AppSizes.radiusFull),
                  borderSide:
                      const BorderSide(color: AppColors.border),
                ),
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                isDense: true,
              ),
              minLines: 1,
              maxLines: 4,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => onSend(),
            ),
          ),

          const SizedBox(width: 8),

          // Send button
          SizedBox(
            width: 40, height: 40,
            child: ElevatedButton(
              onPressed: isStreaming ? null : onSend,
              style: ElevatedButton.styleFrom(
                shape: const CircleBorder(),
                padding: EdgeInsets.zero,
              ),
              child: isStreaming
                  ? const SizedBox(
                      width: 16, height: 16,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.send_rounded, size: 16),
            ),
          ),
        ],
      ),
    );
  }
}
