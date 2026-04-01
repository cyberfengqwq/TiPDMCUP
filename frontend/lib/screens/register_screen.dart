import 'package:flutter/material.dart';
import '../services/api_service.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _userCompanyIdController = TextEditingController();
  final _userIdController = TextEditingController();
  final _usernameController = TextEditingController();
  final _userPasswordController = TextEditingController();

  final _companyIdController = TextEditingController();
  final _companyNameController = TextEditingController();

  bool _isRegisteringUser = false;
  bool _isRegisteringCompany = false;

  @override
  void dispose() {
    _userCompanyIdController.dispose();
    _userIdController.dispose();
    _usernameController.dispose();
    _userPasswordController.dispose();
    _companyIdController.dispose();
    _companyNameController.dispose();
    super.dispose();
  }

  Future<void> _registerUser() async {
    final companyId = _userCompanyIdController.text.trim();
    final userId = _userIdController.text.trim();
    final username = _usernameController.text.trim();
    final password = _userPasswordController.text;

    if (companyId.isEmpty || userId.isEmpty || username.isEmpty || password.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请填写完整的用户注册信息')),
      );
      return;
    }

    setState(() {
      _isRegisteringUser = true;
    });

    final result = await ApiService.registerUser(
      companyId: companyId,
      userId: userId,
      username: username,
      password: password,
    );

    if (!mounted) return;

    setState(() {
      _isRegisteringUser = false;
    });

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(result.message)),
    );

    if (result.success) {
      Navigator.pop(context);
    }
  }

  Future<void> _registerCompany() async {
    final companyId = _companyIdController.text.trim();
    final companyName = _companyNameController.text.trim();

    if (companyId.isEmpty || companyName.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请填写完整的公司注册信息')),
      );
      return;
    }

    setState(() {
      _isRegisteringCompany = true;
    });

    final result = await ApiService.registerCompany(
      companyId: companyId,
      companyName: companyName,
    );

    if (!mounted) return;

    setState(() {
      _isRegisteringCompany = false;
    });

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(result.message)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        backgroundColor: const Color(0xFFF3F4F6),
        appBar: AppBar(
          title: const Text(
            '注册',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
          ),
          backgroundColor: const Color(0xFF1E3A8A),
          bottom: const TabBar(
            labelColor: Colors.white,
            indicatorColor: Colors.white,
            tabs: [
              Tab(text: '注册用户'),
              Tab(text: '注册公司'),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            _buildRegisterUserTab(),
            _buildRegisterCompanyTab(),
          ],
        ),
      ),
    );
  }

  Widget _buildRegisterUserTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        TextField(
          controller: _userCompanyIdController,
          decoration: const InputDecoration(
            labelText: '公司ID',
            border: OutlineInputBorder(),
            filled: true,
            fillColor: Colors.white,
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _userIdController,
          decoration: const InputDecoration(
            labelText: '用户ID',
            border: OutlineInputBorder(),
            filled: true,
            fillColor: Colors.white,
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _usernameController,
          decoration: const InputDecoration(
            labelText: '用户名',
            border: OutlineInputBorder(),
            filled: true,
            fillColor: Colors.white,
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _userPasswordController,
          obscureText: true,
          decoration: const InputDecoration(
            labelText: '密码（至少6位）',
            border: OutlineInputBorder(),
            filled: true,
            fillColor: Colors.white,
          ),
        ),
        const SizedBox(height: 20),
        SizedBox(
          height: 46,
          child: ElevatedButton(
            onPressed: _isRegisteringUser ? null : _registerUser,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF1E3A8A),
              foregroundColor: Colors.white,
            ),
            child: _isRegisteringUser
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : const Text('确认注册用户'),
          ),
        ),
      ],
    );
  }

  Widget _buildRegisterCompanyTab() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        TextField(
          controller: _companyIdController,
          decoration: const InputDecoration(
            labelText: '公司ID',
            border: OutlineInputBorder(),
            filled: true,
            fillColor: Colors.white,
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: _companyNameController,
          decoration: const InputDecoration(
            labelText: '公司名称',
            border: OutlineInputBorder(),
            filled: true,
            fillColor: Colors.white,
          ),
        ),
        const SizedBox(height: 20),
        SizedBox(
          height: 46,
          child: ElevatedButton(
            onPressed: _isRegisteringCompany ? null : _registerCompany,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF1E3A8A),
              foregroundColor: Colors.white,
            ),
            child: _isRegisteringCompany
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : const Text('确认注册公司'),
          ),
        ),
      ],
    );
  }
}
