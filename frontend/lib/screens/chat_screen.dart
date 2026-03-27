import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:photo_view/photo_view.dart';
import '../models/chat_message.dart'; 
import '../services/api_service.dart';

class ChatScreen extends StatefulWidget {
  final SessionInfo session;

  const ChatScreen({Key? key, required this.session}) : super(key: key);

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final String _chatId = 'flutter_${DateTime.now().millisecondsSinceEpoch}';
  final List<ChatMessage> _messages = [
    ChatMessage(
      text: "你好！我是上市公司财报智能问数助手，请问有什么可以帮您？\n例如您能问：\n- 贵州茅台2023年的净利润是多少？\n- 对比下比亚迪和五粮液的研发投入占比。",
      isUser: false,
    )
  ];
  bool _isLoading = false;

  void _sendMessage() async {
    final text = _textController.text.trim();
    if (text.isEmpty) return;

    _textController.clear();
    
    // 1. 添加用户的提问并刷新
    setState(() {
      _messages.add(ChatMessage(text: text, isUser: true));
      _isLoading = true;
    });
    _scrollToBottom();

    // 2. 请求 Python 后端接口
    final String reply = await ApiService.sendMessage(
      text,
      chatId: _chatId,
    );

    // 3. 将回答填入列表
    if (mounted) {
      setState(() {
        _isLoading = false;
        _messages.add(ChatMessage(text: reply, isUser: false)); 
      });
      _scrollToBottom();
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _openImagePreview(String url) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => Scaffold(
          appBar: AppBar(
            backgroundColor: Colors.black,
            iconTheme: const IconThemeData(color: Colors.white),
          ),
          backgroundColor: Colors.black,
          body: PhotoView(
            imageProvider: CachedNetworkImageProvider(url),
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => FocusScope.of(context).unfocus(), // 点击空白处收起键盘
      child: Scaffold(
        backgroundColor: const Color(0xFFF3F4F6), // 浅灰背景色
        appBar: AppBar(
        title: const Text(
          "财报智能问数助手",
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: Colors.white),
        ),
        backgroundColor: const Color(0xFF1E3A8A), // 金融蓝深色
        centerTitle: true,
        elevation: 2,
        actions: [
          Builder(
            builder: (context) {
              return IconButton(
                icon: const Icon(Icons.history, color: Colors.white),
                tooltip: "历史对话",
                onPressed: () {
                  Scaffold.of(context).openEndDrawer();
                },
              );
            },
          ),
        ],
      ),
      endDrawer: Drawer(
        child: SafeArea(
          child: Column(
            children: [
              Container(
                alignment: Alignment.centerLeft,
                padding: const EdgeInsets.all(16.0),
                child: const Text(
                  "历史对话",
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF1E3A8A),
                  ),
                ),
              ),
              const Divider(height: 1),
              Expanded(
                child: ListView(
                  padding: EdgeInsets.zero,
                  children: [
                    ListTile(
                      leading: const Icon(Icons.chat_bubble_outline, color: Colors.grey),
                      title: const Text("贵州茅台2023年财报分析"),
                      subtitle: const Text("昨天"),
                      onTap: () {
                        Navigator.pop(context); // 点击后收起抽屉，后续可在这里添加切换对话逻辑
                      },
                    ),
                    ListTile(
                      leading: const Icon(Icons.chat_bubble_outline, color: Colors.grey),
                      title: const Text("比亚迪和五粮液的研发对比"),
                      subtitle: const Text("2023-08-15"),
                      onTap: () {
                        Navigator.pop(context);
                      },
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
      body: Column(
        children: [
          Expanded(
            child: GestureDetector(
              onTap: () => FocusScope.of(context).unfocus(), // 点击ListView内部也能收起键盘
              child: ListView.builder(
                controller: _scrollController,
                padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 20.0),
              itemCount: _messages.length + (_isLoading ? 1 : 0),
              itemBuilder: (context, index) {
                // 如果正在加载且渲染到最后一项，展示"正在思考"气泡
                if (_isLoading && index == _messages.length) {
                  return _buildLoadingBubble();
                }
                final message = _messages[index];
                return _buildMessageBubble(message);
              },
            ),
          ),
          ),
          _buildInputArea(),
        ],
      ),
    ),
    );
  }

  /// 渲染气泡整体框架
  Widget _buildMessageBubble(ChatMessage msg) {
    final isUser = msg.isUser;
    
    return Padding(
      padding: const EdgeInsets.only(bottom: 24.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          if (!isUser) _buildAvatar(isUser: false),
          if (!isUser) const SizedBox(width: 8),
          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.75, // 宽屏下限制最大宽度
              ),
              decoration: BoxDecoration(
                color: isUser ? const Color(0xFF1E3A8A) : Colors.white,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(16),
                  topRight: const Radius.circular(16),
                  bottomLeft: Radius.circular(isUser ? 16 : 4),
                  bottomRight: Radius.circular(isUser ? 4 : 16),
                ),
                boxShadow: isUser
                    ? null
                    : [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.05),
                          offset: const Offset(0, 2),
                          blurRadius: 6,
                        )
                      ],
              ),
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                   // 1. 文字内容 (Markdown渲染)
                  MarkdownBody(
                    data: msg.text,
                    styleSheet: MarkdownStyleSheet(
                      p: TextStyle(color: isUser ? Colors.white : Colors.black87, fontSize: 15, height: 1.5),
                      strong: TextStyle(color: isUser ? Colors.white : Colors.black, fontWeight: FontWeight.w600),
                    ),
                  ),
                  
                  // 2. 渲染可视化图表
                  if (!isUser && msg.images != null && msg.images!.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: msg.images!.map((url) {
                        return GestureDetector(
                          onTap: () => _openImagePreview(url),
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(8),
                            child: CachedNetworkImage(
                              imageUrl: url,
                              width: 200,
                              fit: BoxFit.cover,
                              placeholder: (context, url) => Container(
                                width: 200, height: 120,
                                color: Colors.grey.shade200,
                                child: const Center(child: CircularProgressIndicator(strokeWidth: 2)),
                              ),
                              errorWidget: (context, url, error) => Container(
                                width: 200, height: 120,
                                color: Colors.grey.shade200,
                                child: const Icon(Icons.broken_image, color: Colors.grey),
                              ),
                            ),
                          ),
                        );
                      }).toList(),
                    ),
                  ],

                  // 3. 渲染参考文献卡片
                  if (!isUser && msg.references != null && msg.references!.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    Divider(color: Colors.grey.shade300, height: 1),
                    const SizedBox(height: 12),
                    const Text("📝 参考文献", style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.grey)),
                    const SizedBox(height: 8),
                    ...msg.references!.map((ref) => Container(
                          margin: const EdgeInsets.only(bottom: 8),
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: Colors.blueGrey.withOpacity(0.05),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: Colors.blueGrey.withOpacity(0.1)),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(ref.paperPath.split('/').last, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12, color: Color(0xFF1E3A8A))),
                              const SizedBox(height: 4),
                              Text(ref.text, maxLines: 3, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, color: Colors.black54)),
                            ],
                          ),
                        )),
                  ]
                ],
              ),
            ),
          ),
          if (isUser) const SizedBox(width: 8),
          if (isUser) _buildAvatar(isUser: true),
        ],
      ),
    );
  }

  /// 渲染头像
  Widget _buildAvatar({required bool isUser}) {
    return CircleAvatar(
      radius: 18,
      backgroundColor: isUser ? const Color(0xFF1E3A8A).withOpacity(0.1) : Colors.white,
      child: Icon(
        isUser ? Icons.person : Icons.smart_toy,
        color: isUser ? const Color(0xFF1E3A8A) : Colors.blueGrey.shade700,
        size: 20,
      ),
    );
  }

  /// 渲染加载动画状态气泡
  Widget _buildLoadingBubble() {
    return Padding(
      padding: const EdgeInsets.only(bottom: 24.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildAvatar(isUser: false),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(16), topRight: Radius.circular(16),
                bottomLeft: Radius.circular(4), bottomRight: Radius.circular(16),
              ),
              boxShadow: [
                BoxShadow(color: Colors.black.withOpacity(0.05), offset: const Offset(0, 2), blurRadius: 6)
              ],
            ),
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                 SizedBox(
                   width: 14, height: 14, 
                   child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF1E3A8A))
                 ),
                 SizedBox(width: 10),
                 Text("正在深度解析财报数据...", style: TextStyle(color: Colors.grey, fontSize: 13)),
              ],
            ),
          )
        ],
      ),
    );
  }

  /// 底部输入框
  Widget _buildInputArea() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            offset: const Offset(0, -2),
            blurRadius: 10,
          )
        ],
      ),
      child: SafeArea(
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _textController,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _sendMessage(),
                decoration: InputDecoration(
                  hintText: "向智能助手提问，例如：贵州茅台去年的净利润是多少？",
                  hintStyle: TextStyle(color: Colors.grey.shade400, fontSize: 14),
                  filled: true,
                  fillColor: const Color(0xFFF3F4F6),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Container(
              decoration: const BoxDecoration(
                color: Color(0xFF1E3A8A),
                shape: BoxShape.circle,
              ),
              child: IconButton(
                onPressed: _isLoading ? null : _sendMessage,
                icon: const Icon(Icons.send_rounded, color: Colors.white),
                tooltip: "发送",
              ),
            ),
          ],
        ),
      ),
    );
  }
}