import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import '../../../core/constants/app_colors.dart';
import '../../../core/constants/app_sizes.dart';
import '../../../core/constants/app_text_styles.dart';

/// Live streaming message bubble — shows growing text + blinking cursor.
class StreamingBubble extends StatefulWidget {
  final String content;
  const StreamingBubble({super.key, required this.content});

  @override
  State<StreamingBubble> createState() => _StreamingBubbleState();
}

class _StreamingBubbleState extends State<StreamingBubble>
    with SingleTickerProviderStateMixin {
  late AnimationController _blink;
  bool _cursorVisible = true;

  @override
  void initState() {
    super.initState();
    _blink = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 530),
    )..addStatusListener((s) {
        if (s == AnimationStatus.completed) {
          setState(() => _cursorVisible = !_cursorVisible);
          _blink.reset();
          _blink.forward();
        }
      });
    _blink.forward();
  }

  @override
  void dispose() {
    _blink.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final displayText = widget.content +
        (_cursorVisible ? '\u2588' : ' '); // block cursor char

    return Container(
      constraints: const BoxConstraints(maxWidth: AppSizes.bubbleMaxWidth),
      margin: const EdgeInsets.only(bottom: 20),
      padding: const EdgeInsets.all(AppSizes.bubblePadH),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(4),
          topRight: Radius.circular(AppSizes.radiusLG),
          bottomLeft: Radius.circular(AppSizes.radiusLG),
          bottomRight: Radius.circular(AppSizes.radiusLG),
        ),
        border: Border.all(color: AppColors.primaryBorder),
        boxShadow: [
          BoxShadow(
            color: AppColors.primary.withOpacity(0.04),
            blurRadius: 8, offset: const Offset(0, 2),
          ),
        ],
      ),
      child: widget.content.isEmpty
          ? _TypingIndicator()
          : MarkdownBody(
              data: displayText,
              styleSheet: MarkdownStyleSheet(
                p: AppTextStyles.bodyMedium,
              ),
            ),
    );
  }
}

/// Three animated dots shown while the backend processes before first token.
class _TypingIndicator extends StatefulWidget {
  @override
  State<_TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<_TypingIndicator>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) {
        final v = _ctrl.value;
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: List.generate(3, (i) {
            final phase = (v - i * 0.15).clamp(0.0, 1.0);
            final opacity = (phase < 0.5 ? phase * 2 : (1 - phase) * 2).clamp(0.3, 1.0);
            return Padding(
              padding: const EdgeInsets.only(right: 4),
              child: Opacity(
                opacity: opacity,
                child: Container(
                  width: 7, height: 7,
                  decoration: const BoxDecoration(
                    color: AppColors.primary, shape: BoxShape.circle),
                ),
              ),
            );
          }),
        );
      },
    );
  }
}
