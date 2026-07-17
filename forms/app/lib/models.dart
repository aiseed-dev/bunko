class Contact {
  final int remoteId;
  final String pulledAt;
  final String createdAt;
  final String? email;
  final String payload;
  final bool confirmed;
  final bool handled;

  Contact({
    required this.remoteId,
    required this.pulledAt,
    required this.createdAt,
    required this.email,
    required this.payload,
    required this.confirmed,
    required this.handled,
  });

  factory Contact.fromRow(Map<String, Object?> row) {
    return Contact(
      remoteId: row['remote_id'] as int,
      pulledAt: row['pulled_at'] as String,
      createdAt: row['created_at'] as String,
      email: row['email'] as String?,
      payload: row['payload'] as String,
      confirmed: (row['confirmed'] as int) != 0,
      handled: (row['handled'] as int) != 0,
    );
  }
}
