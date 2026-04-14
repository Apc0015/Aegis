import 'dart:async';
import 'dart:convert';
import 'package:dio/dio.dart';

/// Discriminated union for SSE events from the RAPID streaming endpoint.
sealed class SseEvent {}

class SseToken extends SseEvent {
  final String token;
  SseToken(this.token);
}

class SseResult extends SseEvent {
  final Map<String, dynamic> data;
  SseResult(this.data);
}

class SseDone extends SseEvent {}

class SseError extends SseEvent {
  final String message;
  SseError(this.message);
}

/// Streams SSE events from GET /api/v1/query/stream.
///
/// Protocol (per api/routers/query.py):
///   data: <plain token>           → SseToken
///   data: <JSON QueryResult>      → SseResult
///   data: [DONE]                  → SseDone
///   data: {"error": "..."}        → SseError
class SseClient {
  final Dio _dio;

  const SseClient(this._dio);

  Stream<SseEvent> stream({
    required String userQuery,
    required String projectId,
    required String ragMode,
    String mode = 'auto',
    bool forceDb = false,
    bool llmIntent = false,
  }) async* {
    late Response<ResponseBody> response;

    try {
      response = await _dio.get<ResponseBody>(
        '/api/v1/query/stream',
        queryParameters: {
          'user_query': userQuery,
          'project_id': projectId,
          'rag_mode': ragMode,
          'mode': mode,
          'force_db': forceDb,
          'llm_intent': llmIntent,
        },
        options: Options(
          responseType: ResponseType.stream,
          headers: {'Accept': 'text/event-stream'},
          receiveTimeout: const Duration(minutes: 5),
        ),
      );
    } catch (e) {
      yield SseError('Failed to connect to streaming endpoint: $e');
      return;
    }

    // Transform byte stream → UTF-8 lines → SSE data frames
    final lineStream = response.data!.stream
        .cast<List<int>>()
        .transform(const Utf8Decoder(allowMalformed: true))
        .transform(const LineSplitter());

    await for (final line in lineStream) {
      if (!line.startsWith('data: ')) continue;

      final payload = line.substring(6); // strip "data: "

      if (payload == '[DONE]') {
        yield SseDone();
        return;
      }

      // Try JSON parse — if it succeeds it's the final QueryResult (or an error obj)
      try {
        final json = jsonDecode(payload) as Map<String, dynamic>;
        if (json.containsKey('error')) {
          yield SseError(json['error'].toString());
        } else {
          yield SseResult(json);
        }
        // After the result object, we expect [DONE] next — keep iterating
      } catch (_) {
        // Plain token — un-escape newlines that were escaped for SSE framing
        final token = payload.replaceAll(r'\n', '\n');
        if (token.isNotEmpty) yield SseToken(token);
      }
    }
  }
}
