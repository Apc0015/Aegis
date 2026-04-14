import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'app_colors.dart';

/// RAPID Text Styles — Inter font throughout
abstract class AppTextStyles {
  // ── Display / headings ────────────────────────────────────────────────────────
  static TextStyle get displayLarge => GoogleFonts.inter(
    fontSize: 32, fontWeight: FontWeight.w800,
    color: AppColors.textPrimary, letterSpacing: -0.5,
  );

  static TextStyle get displayMedium => GoogleFonts.inter(
    fontSize: 24, fontWeight: FontWeight.w700,
    color: AppColors.textPrimary, letterSpacing: -0.3,
  );

  static TextStyle get displaySmall => GoogleFonts.inter(
    fontSize: 20, fontWeight: FontWeight.w700,
    color: AppColors.textPrimary, letterSpacing: -0.2,
  );

  // ── Headlines ─────────────────────────────────────────────────────────────────
  static TextStyle get headlineLarge => GoogleFonts.inter(
    fontSize: 18, fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
  );

  static TextStyle get headlineMedium => GoogleFonts.inter(
    fontSize: 16, fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
  );

  static TextStyle get headlineSmall => GoogleFonts.inter(
    fontSize: 14, fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
  );

  // ── Body ──────────────────────────────────────────────────────────────────────
  static TextStyle get bodyLarge => GoogleFonts.inter(
    fontSize: 15, fontWeight: FontWeight.w400,
    color: AppColors.textPrimary, height: 1.6,
  );

  static TextStyle get bodyMedium => GoogleFonts.inter(
    fontSize: 14, fontWeight: FontWeight.w400,
    color: AppColors.textPrimary, height: 1.5,
  );

  static TextStyle get bodySmall => GoogleFonts.inter(
    fontSize: 13, fontWeight: FontWeight.w400,
    color: AppColors.textSecondary, height: 1.4,
  );

  // ── Labels ────────────────────────────────────────────────────────────────────
  static TextStyle get labelLarge => GoogleFonts.inter(
    fontSize: 14, fontWeight: FontWeight.w500,
    color: AppColors.textPrimary,
  );

  static TextStyle get labelMedium => GoogleFonts.inter(
    fontSize: 12, fontWeight: FontWeight.w500,
    color: AppColors.textSecondary, letterSpacing: 0.1,
  );

  static TextStyle get labelSmall => GoogleFonts.inter(
    fontSize: 11, fontWeight: FontWeight.w500,
    color: AppColors.textMuted, letterSpacing: 0.2,
  );

  // ── Captions / metadata ───────────────────────────────────────────────────────
  static TextStyle get caption => GoogleFonts.inter(
    fontSize: 12, fontWeight: FontWeight.w400,
    color: AppColors.textMuted,
  );

  static TextStyle get mono => const TextStyle(
    fontFamily: 'monospace', fontSize: 13,
    color: AppColors.textPrimary,
  );

  // ── Logo / brand ──────────────────────────────────────────────────────────────
  static TextStyle get logoStyle => GoogleFonts.inter(
    fontSize: 20, fontWeight: FontWeight.w800,
    color: AppColors.textPrimary, letterSpacing: -0.5,
  );

  static TextStyle get logoAccent => GoogleFonts.inter(
    fontSize: 20, fontWeight: FontWeight.w800,
    color: AppColors.primary, letterSpacing: -0.5,
  );

  // ── Buttons ───────────────────────────────────────────────────────────────────
  static TextStyle get buttonPrimary => GoogleFonts.inter(
    fontSize: 14, fontWeight: FontWeight.w600,
    color: AppColors.textInverse,
  );

  static TextStyle get buttonSecondary => GoogleFonts.inter(
    fontSize: 14, fontWeight: FontWeight.w500,
    color: AppColors.primary,
  );
}
