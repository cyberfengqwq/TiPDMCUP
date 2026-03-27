import 'dart:convert';
import 'package:http/http.dart' as http;

class LoginResult {
  final bool success;
  final String message;
  final Map<String, dynamic>? user;

  const LoginResult({
    required this.success,
    required this.message,
    this.user,
  });
}

class ApiService {
  // 【重要】因为您在使用真机调试，这里必须填入您 Mac 电脑的局域网 IPv4 地址！
  // 例如: 'http://192.168.1.100:5000' (视您的Python后端端口而定)
  static const String baseUrl = 'http://101.37.80.57:1516';

  static Future<LoginResult> login({
    required String company,
    required String account,
    required String password,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/login'),
        headers: {
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'company': company,
          'name': account,
          'password': password,
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
        final dynamic userData = data?['user'];
        return LoginResult(
          success: true,
          message: data?['message']?.toString() ?? '登录成功',
          user: userData is Map<String, dynamic> ? userData : null,
        );
      }

      return LoginResult(
        success: false,
        message: data?['message']?.toString() ?? '登录失败，状态码: ${response.statusCode}',
      );
    } catch (e) {
      return LoginResult(success: false, message: '网络请求发生错误: $e');
    }
  }

  static Future<String> sendMessage(
    String prompt, {
    required String sessionId,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/chat'),
        headers: {
          'Content-Type': 'application/json', // 假设您的后端接收 JSON
        },
        body: jsonEncode({
          'prompt': prompt,
          'session_id': sessionId,
        }),
      );

      if (response.statusCode == 200) {
        // 解决中文乱码问题
        final decodedBody = utf8.decode(response.bodyBytes);
        
        // 如果您的后端直接返回纯字符串：
        return decodedBody;
        
        // 如果您的后端返回的是 JSON 格式，如 {"message": "你好"}，请改成下面这样解包：
        // final jsonResponse = jsonDecode(decodedBody);
        // return jsonResponse['message'] ?? '无返回内容';
      } else {
        return '请求失败，状态码: ${response.statusCode}';
      }
    } catch (e) {
      return '网络请求发生错误: $e';
    }
  }
}