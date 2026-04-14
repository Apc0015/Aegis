import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/network/api_client.dart';
import '../data/datasources/rapid_api_datasource.dart';

/// Singleton Dio client shared across all providers.
final dioProvider = Provider((ref) => buildDioClient());

/// Singleton API datasource.
final apiDataSourceProvider = Provider((ref) {
  return RapidApiDataSource(ref.watch(dioProvider));
});
