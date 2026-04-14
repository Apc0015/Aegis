import 'package:flutter/material.dart';
import '../../core/constants/app_text_styles.dart';

class RapidLogo extends StatelessWidget {
  const RapidLogo({super.key});

  @override
  Widget build(BuildContext context) {
    return RichText(
      text: TextSpan(
        children: [
          TextSpan(text: 'R', style: AppTextStyles.logoAccent),
          TextSpan(text: 'APID', style: AppTextStyles.logoStyle),
        ],
      ),
    );
  }
}
