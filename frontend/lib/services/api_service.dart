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

class ActionResult {
  final bool success;
  final String message;

  const ActionResult({
    required this.success,
    required this.message,
  });
}

class ApiService {
  static const String baseUrl = 'http://101.37.80.57:1516';
  static const Duration _timeout = Duration(seconds: 45);
  static SessionInfo? _currentSession;
  static String? _activeChatId;

  static SessionInfo? get currentSession => _currentSession;

  static void bindActiveChat(String chatId) {
    _activeChatId = chatId;
  }

  static String _extractErrorMessage(Map<String, dynamic>? data, int statusCode, String fallback) {
    return data?['detail']?.toString() ??
        data?['message']?.toString() ??
        '$fallback，状态码: $statusCode';
  }

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
          // 后端字段当前为 company_id（后端拼写如此）
          'company_id': companyId,
        }),
      ).timeout(_timeout);

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
        message: _extractErrorMessage(data, response.statusCode, '登录失败'),
      );
    } catch (e) {
      return LoginResult(success: false, message: '网络请求发生错误: $e');
    }
  }

  static Future<Map<String, dynamic>> sendMessage(String prompt, {
    required String chatId,
    String problemId = 'B0000',
    int task = 2,
    bool isEnd = false,
  }) async {
    try {
      final sessionId = _currentSession?.sessionId;
      if (sessionId == null || sessionId.isEmpty) {
        return {'content': '未登录或会话已失效，请重新登录', 'image': [], 'references': []};
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
          'problem_id': problemId,
          'task': task,
          'is_end': isEnd,
        }),
      );

      _activeChatId = chatId;

      if (response.statusCode == 200) {
        final decodedBody = utf8.decode(response.bodyBytes);
        try {
          return jsonDecode(decodedBody) as Map<String, dynamic>;
        } catch (_) {
          return {'content': decodedBody, 'image': [], 'references': []};
        }
      } else {
        final decodedBody = utf8.decode(response.bodyBytes);
        String errorMsg;
        try {
          final jsonResponse = jsonDecode(decodedBody) as Map<String, dynamic>;
          errorMsg = _extractErrorMessage(jsonResponse, response.statusCode, '请求失败');
        } catch (_) {
          errorMsg = '请求失败，状态码: ${response.statusCode}';
        }
        return {'content': errorMsg, 'image': [], 'references': []};
      }
    } catch (e) {
      return {'content': '网络请求发生错误: $e', 'image': [], 'references': []};
    }
  }

  static Future<bool> logout({String? chatId}) async {
    final sessionId = _currentSession?.sessionId;
    final targetChatId = chatId ?? _activeChatId;

    if (sessionId == null || sessionId.isEmpty) {
      _currentSession = null;
      _activeChatId = null;
      return true;
    }

    try {
      final response = await http.post(
        Uri.parse('$baseUrl/logout'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $sessionId',
        },
        body: jsonEncode({
          if (targetChatId != null && targetChatId.isNotEmpty) 'chat_id': targetChatId,
        }),
      ).timeout(_timeout);
      _currentSession = null;
      _activeChatId = null;
      return response.statusCode == 200;
    } catch (_) {
      _currentSession = null;
      _activeChatId = null;
      return false;
    }
  }

  static Future<ActionResult> registerUser({
    required String companyId,
    required String userId,
    required String username,
    required String password,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/register'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'company_id': companyId,
          'user_id': userId,
          'username': username,
          'password': password,
        }),
      ).timeout(_timeout);

      final decodedBody = utf8.decode(response.bodyBytes);
      Map<String, dynamic>? data;
      try {
        data = jsonDecode(decodedBody) as Map<String, dynamic>;
      } catch (_) {
        data = null;
      }

      if (response.statusCode == 200) {
        return ActionResult(
          success: true,
          message: data?['message']?.toString() ?? '注册成功',
        );
      }

      return ActionResult(
        success: false,
        message: _extractErrorMessage(data, response.statusCode, '注册失败'),
      );
    } catch (e) {
      return ActionResult(success: false, message: '网络请求发生错误: $e');
    }
  }

  static Future<ActionResult> registerCompany({
    required String companyId,
    required String companyName,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/register/company'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'company_id': companyId,
          'company_name': companyName,
        }),
      ).timeout(_timeout);

      final decodedBody = utf8.decode(response.bodyBytes);
      Map<String, dynamic>? data;
      try {
        data = jsonDecode(decodedBody) as Map<String, dynamic>;
      } catch (_) {
        data = null;
      }

      if (response.statusCode == 200) {
        return ActionResult(
          success: true,
          message: data?['message']?.toString() ?? '公司注册成功',
        );
      }

      return ActionResult(
        success: false,
        message: _extractErrorMessage(data, response.statusCode, '公司注册失败'),
      );
    } catch (e) {
      return ActionResult(success: false, message: '网络请求发生错误: $e');
    }
  }
}
