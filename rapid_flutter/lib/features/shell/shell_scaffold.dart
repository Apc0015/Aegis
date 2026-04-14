import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_sizes.dart';
import 'sidebar_nav.dart';
import 'top_bar.dart';

class ShellScaffold extends ConsumerWidget {
  final Widget child;
  const ShellScaffold({super.key, required this.child});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final width = MediaQuery.of(context).size.width;
    final isNarrow = width < AppSizes.tabletBreak;

    return Scaffold(
      backgroundColor: AppColors.background,
      drawer: isNarrow
          ? Drawer(
              backgroundColor: AppColors.sidebarBg,
              shape: const RoundedRectangleBorder(),
              child: const SidebarNav(isDrawer: true),
            )
          : null,
      body: Column(
        children: [
          // ── Top bar ──────────────────────────────────────────────────────────
          const TopBar(),
          // ── Main content ─────────────────────────────────────────────────────
          Expanded(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Sidebar (hidden on narrow screens)
                if (!isNarrow)
                  const SidebarNav(),
                // Page content
                Expanded(
                  child: ClipRect(child: child),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
