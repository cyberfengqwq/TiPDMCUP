class ChatMessage {
  final String text; // 用户提问 或 AI的文字回答
  final bool isUser; // 判断是用户还是AI
  final List<String>? images; // 图片列表（AI专属）
  final List<ChatReference>? references; // 参考文献列表（AI专属）

  ChatMessage({
    required this.text,
    required this.isUser,
    this.images,
    this.references,
  });

  /// 方便从后端 Q&A 风格的 JSON 一次性解析生成一问一答（两条消息）
  static List<ChatMessage> fromQAPairJson(Map<String, dynamic> json) {
    final String question = json['Q'] ?? '';
    final Map<String, dynamic>? answerNode = json['A'];
    
    // 生成用户的提问消息
    final userMsg = ChatMessage(
      text: question,
      isUser: true,
    );

    // 如果还没有生成回答，只返回提问（应对可能的增量/异步流加载场景）
    if (answerNode == null) {
      return [userMsg];
    }

    // 解析图片与参考文献
    final List<dynamic>? imageList = answerNode['image'];
    final List<dynamic>? refList = answerNode['references'];

    final aiMsg = ChatMessage(
      text: answerNode['content'] ?? '',
      isUser: false,
      images: imageList?.map((e) => e.toString()).toList(),
      references: refList?.map((e) => ChatReference.fromJson(e as Map<String, dynamic>)).toList(),
    );

    return [userMsg, aiMsg];
  }
}

class ChatReference {
  final String paperPath;
  final String text;

  ChatReference({
    required this.paperPath,
    required this.text,
  });

  factory ChatReference.fromJson(Map<String, dynamic> json) {
    return ChatReference(
      paperPath: json['paper_path'] ?? '',
      text: json['text'] ?? '',
    );
  }
}
