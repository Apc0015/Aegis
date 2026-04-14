import 'package:flutter/material.dart';

/// RAPID Design System — Light & Minimal (Stripe / Figma aesthetic)
abstract class AppColors {
  // ── Page background ──────────────────────────────────────────────────────────
  static const Color background       = Color(0xFFF9FAFB); // gray-50
  static const Color surface          = Color(0xFFFFFFFF); // white
  static const Color surfaceVariant   = Color(0xFFF3F4F6); // gray-100

  // ── Sidebar ───────────────────────────────────────────────────────────────────
  static const Color sidebarBg        = Color(0xFFF3F4F6); // gray-100
  static const Color sidebarBorder    = Color(0xFFE5E7EB); // gray-200
  static const Color sidebarSelected  = Color(0xFFEEF2FF); // indigo-50
  static const Color sidebarSelBorder = Color(0xFF6366F1); // indigo-500

  // ── Border ────────────────────────────────────────────────────────────────────
  static const Color border           = Color(0xFFE5E7EB); // gray-200
  static const Color borderFocus      = Color(0xFF6366F1); // indigo-500

  // ── Text ──────────────────────────────────────────────────────────────────────
  static const Color textPrimary      = Color(0xFF111827); // gray-900
  static const Color textSecondary    = Color(0xFF6B7280); // gray-500
  static const Color textMuted        = Color(0xFF9CA3AF); // gray-400
  static const Color textInverse      = Color(0xFFFFFFFF);

  // ── Brand / Accent (Indigo) ───────────────────────────────────────────────────
  static const Color primary          = Color(0xFF6366F1); // indigo-500
  static const Color primaryDark      = Color(0xFF4F46E5); // indigo-600
  static const Color primaryLight     = Color(0xFFEEF2FF); // indigo-50
  static const Color primaryBorder    = Color(0xFFC7D2FE); // indigo-200

  // ── Confidence verdicts ───────────────────────────────────────────────────────
  static const Color highText         = Color(0xFF15803D); // green-700
  static const Color highBg           = Color(0xFFF0FDF4); // green-50
  static const Color highBorder       = Color(0xFFBBF7D0); // green-200

  static const Color mediumText       = Color(0xFFA16207); // yellow-700
  static const Color mediumBg         = Color(0xFFFEFCE8); // yellow-50
  static const Color mediumBorder     = Color(0xFFFEF08A); // yellow-200

  static const Color lowText          = Color(0xFFB91C1C); // red-700
  static const Color lowBg            = Color(0xFFFEF2F2); // red-50
  static const Color lowBorder        = Color(0xFFFECACA); // red-200

  // ── Routing path colors ───────────────────────────────────────────────────────
  static const Color routeDirect      = Color(0xFF059669); // emerald-600
  static const Color routeDisclaimer  = Color(0xFFD97706); // amber-600
  static const Color routeWeb         = Color(0xFF2563EB); // blue-600
  static const Color routeRefuse      = Color(0xFFDC2626); // red-600
  static const Color routeDenied      = Color(0xFF7C3AED); // violet-600

  // ── Status ────────────────────────────────────────────────────────────────────
  static const Color success          = Color(0xFF059669);
  static const Color successBg        = Color(0xFFF0FDF4);
  static const Color warning          = Color(0xFFD97706);
  static const Color warningBg        = Color(0xFFFFFBEB);
  static const Color error            = Color(0xFFDC2626);
  static const Color errorBg          = Color(0xFFFEF2F2);
  static const Color info             = Color(0xFF2563EB);
  static const Color infoBg           = Color(0xFFEFF6FF);

  // ── Role badge colors ─────────────────────────────────────────────────────────
  static const Color roleAdmin        = Color(0xFF7C3AED); // violet-700
  static const Color roleAdminBg      = Color(0xFFF5F3FF); // violet-50
  static const Color roleManager      = Color(0xFF2563EB); // blue-600
  static const Color roleManagerBg    = Color(0xFFEFF6FF); // blue-50
  static const Color roleEmployee     = Color(0xFF059669); // emerald-600
  static const Color roleEmployeeBg   = Color(0xFFF0FDF4); // emerald-50

  // ── User message bubble ───────────────────────────────────────────────────────
  static const Color userBubble       = Color(0xFF6366F1); // indigo-500
  static const Color userBubbleText   = Color(0xFFFFFFFF);

  // ── Confidence verdict aliases (shorthand) ───────────────────────────────────
  static const Color highConf          = highText;
  static const Color highConfBg        = highBg;
  static const Color mediumConf        = mediumText;
  static const Color mediumConfBg      = mediumBg;
  static const Color lowConf           = lowText;
  static const Color lowConfBg         = lowBg;

  // ── Skeleton / shimmer ────────────────────────────────────────────────────────
  static const Color shimmerBase      = Color(0xFFF3F4F6);
  static const Color shimmerHighlight = Color(0xFFFFFFFF);

  // ── Overlay ───────────────────────────────────────────────────────────────────
  static const Color overlay          = Color(0x80000000); // 50% black
}
