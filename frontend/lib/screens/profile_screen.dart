import 'package:flutter/material.dart';
import 'login_screen.dart';
import '../services/api_service.dart';

class ProfileScreen extends StatefulWidget {
  final SessionInfo session;

  const ProfileScreen({super.key, required this.session});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  bool _isLoggingOut = false;

  Future<void> _logout(BuildContext context) async {
    setState(() {
      _isLoggingOut = true;
    });

    final ok = await ApiService.logout();

    if (!context.mounted) return;

    if (!ok) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('退出接口异常，已在本地清理会话')),
      );
    }

    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (context) => const LoginScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF3F4F6),
      appBar: AppBar(
        title: const Text("我的账户", style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
        backgroundColor: const Color(0xFF1E3A8A),
        centerTitle: true,
        elevation: 0,
      ),
      body: ListView(
        padding: const EdgeInsets.all(16.0),
        children: [
          const CircleAvatar(
            radius: 40,
            backgroundColor: Color(0xFF1E3A8A),
            child: Icon(Icons.person, size: 40, color: Colors.white),
          ),
          const SizedBox(height: 16),
          Center(
            child: Text("用户 ${widget.session.userId}", style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          ),
          Center(
            child: Text("所属机构：${widget.session.companyId}", style: const TextStyle(fontSize: 14, color: Colors.grey)),
          ),
          const SizedBox(height: 4),
          Center(
            child: Text(
              "角色：${widget.session.roles.isEmpty ? 'member' : widget.session.roles.join(', ')}",
              style: const TextStyle(fontSize: 13, color: Colors.grey),
            ),
          ),
          const SizedBox(height: 4),
          Center(
            child: Text(
              "会话到期：${widget.session.expiresAt}",
              style: const TextStyle(fontSize: 12, color: Colors.grey),
            ),
          ),
          const SizedBox(height: 16),
          ListTile(
            leading: const Icon(Icons.settings),
            title: const Text("系统设置"),
            trailing: const Icon(Icons.chevron_right),
            tileColor: Colors.white,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            onTap: () {},
          ),
          const SizedBox(height: 32),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red[50],
              foregroundColor: Colors.red,
              minimumSize: const Size(double.infinity, 48),
            ),
            onPressed: _isLoggingOut ? null : () => _logout(context),
            child: _isLoggingOut
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text("退出登录"),
          ),
        ],
      ),
    );
  }
}