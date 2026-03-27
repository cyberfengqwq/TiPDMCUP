import 'dart:convert';
import 'package:http/http.dart' as http;

class SessionInfo {
  final String sessionId;
  final String userId;
  final String companyId;
  final List<String> roles;
  final String expiresAt;

  const SessionInfo({
    required this.sessionId,
    required this.userId,
    required this.companyId,
    required this.roles,
    required this.expiresAt,
  });

  factory SessionInfo.fromJson(Map<String, dynamic> json) {
    final dynamic rawRoles = json['roles'];
    return SessionInfo(
      sessionId: json['session_id']?.toString() ?? '',
      userId: json['user_id']?.toString() ?? '',
      companyId: json['company_id']?.toString() ?? '',
      roles: rawRoles is List ? rawRoles.map((e) => e.toString()).toList() : const [],
      expiresAt: json['expires_at']?.toString() ?? '',
    );
  }
}

class LoginResult {
  final bool success;
  final String message;
  final SessionInfo? session;

  const LoginResult({
    required this.success,
    required this.message,
    this.session,
  });
}

class ApiService {
  static const String baseUrl = 'http://101.37.80.57:1516';
  static SessionInfo? _currentSession;

  static SessionInfo? get currentSession => _currentSession;

  static Future<LoginResult> login({
    required String companyId,
    required String userId,
    required String password,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/login'),
        headers: {
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'user_id': userId,
          'password': password,
          // 后端字段当前为 compay_id（后端拼写如此）
          'compay_id': companyId,
        }),
      );

      final decodedBody = utf8.decode(response.bodyBytes);
      Map<String, dynamic>? data;
      try {
        data = jsonDecode(decodedBody) as Map<String, dynamic>;
      } catch (_) {
        data = null;
      }

      if (response.statusCode == 200) {
        final session = data == null ? null : SessionInfo.fromJson(data);
        _currentSession = session;
        return LoginResult(
          success: true,
          message: '登录成功',
          session: session,
        );
      }

      return LoginResult(
        success: false,
        message: data?['detail']?.toString() ?? '登录失败，状态码: ${response.statusCode}',
      );
    } catch (e) {
      return LoginResult(success: false, message: '网络请求发生错误: $e');
    }
  }

  static Future<String> sendMessage(String prompt, {
    required String chatId,
    bool isEnd = false,
  }) async {
    try {
      final sessionId = _currentSession?.sessionId;
      if (sessionId == null || sessionId.isEmpty) {
        return '未登录或会话已失效，请重新登录';
      }

      final response = await http.post(
        Uri.parse('$baseUrl/chat'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $sessionId',
        },
        body: jsonEncode({
          'prompt': prompt,
          'chat_id': chatId,
          'is_end': isEnd,
        }),
      );

      if (response.statusCode == 200) {
        final decodedBody = utf8.decode(response.bodyBytes);
        try {
          final jsonResponse = jsonDecode(decodedBody) as Map<String, dynamic>;
          return jsonResponse['answer']?.toString() ?? '无返回内容';
        } catch (_) {
          return decodedBody;
        }
      } else {
        final decodedBody = utf8.decode(response.bodyBytes);
        try {
          final jsonResponse = jsonDecode(decodedBody) as Map<String, dynamic>;
          return jsonResponse['detail']?.toString() ?? '请求失败，状态码: ${response.statusCode}';
        } catch (_) {
          return '请求失败，状态码: ${response.statusCode}';
        }
      }
    } catch (e) {
      return '网络请求发生错误: $e';
    }
  }

  static Future<bool> logout() async {
    final sessionId = _currentSession?.sessionId;
    if (sessionId == null || sessionId.isEmpty) {
      _currentSession = null;
      return true;
    }

    try {
      final response = await http.post(
        Uri.parse('$baseUrl/logout'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $sessionId',
        },
        body: jsonEncode({}),
      );
      _currentSession = null;
      return response.statusCode == 200;
    } catch (_) {
      _currentSession = null;
      return false;
    }
  }
}