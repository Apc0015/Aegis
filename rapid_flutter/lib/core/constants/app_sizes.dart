/// RAPID Layout Sizes & Spacing Constants
abstract class AppSizes {
  // ── Sidebar ───────────────────────────────────────────────────────────────────
  static const double sidebarWidth        = 220.0;
  static const double sidebarCollapsed    = 56.0;

  // ── TopBar ────────────────────────────────────────────────────────────────────
  static const double topBarHeight        = 56.0;

  // ── Breakpoints ───────────────────────────────────────────────────────────────
  static const double mobileBreak         = 600.0;
  static const double tabletBreak         = 900.0;
  static const double desktopBreak        = 1200.0;

  // Aliases used by some widgets
  static const double breakpointMobile    = mobileBreak;
  static const double breakpointTablet    = tabletBreak;
  static const double breakpointDesktop   = desktopBreak;

  // ── Content max width ─────────────────────────────────────────────────────────
  static const double contentMaxWidth     = 900.0;
  static const double chatMaxWidth        = 720.0;

  // ── Padding ───────────────────────────────────────────────────────────────────
  static const double paddingXS           = 4.0;
  static const double paddingSM           = 8.0;
  static const double paddingMD           = 16.0;
  static const double paddingLG           = 24.0;
  static const double paddingXL           = 32.0;
  static const double paddingXXL          = 48.0;

  // ── Border radius ─────────────────────────────────────────────────────────────
  static const double radiusXS            = 4.0;
  static const double radiusSM            = 6.0;
  static const double radiusMD            = 8.0;
  static const double radiusLG            = 12.0;
  static const double radiusXL            = 16.0;
  static const double radiusFull          = 999.0;

  // ── Icon sizes ────────────────────────────────────────────────────────────────
  static const double iconSM              = 14.0;
  static const double iconMD              = 18.0;
  static const double iconLG              = 22.0;

  // ── Card elevation ────────────────────────────────────────────────────────────
  static const double cardElevation       = 0.0;  // we use border, not shadow
  static const double cardElevationHover  = 2.0;

  // ── Chat bubbles ──────────────────────────────────────────────────────────────
  static const double bubbleMaxWidth      = 680.0;
  static const double bubblePadH         = 16.0;
  static const double bubblePadV         = 12.0;

  // ── Input bar ────────────────────────────────────────────────────────────────
  static const double inputBarHeight      = 64.0;
  static const double inputBarPadH       = 16.0;
}
