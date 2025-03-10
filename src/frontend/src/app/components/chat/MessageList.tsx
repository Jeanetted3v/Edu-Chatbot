interface Message {
  id: string;
  content: string;
  sender: 'user' | 'bot' | 'staff';
  timestamp: Date;
  className?: string;
}

interface MessageListProps {
  messages: Message[];
}

export default function MessageList({ messages }: MessageListProps) {
  return (
    <div className="space-y-4">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`p-2 rounded ${
            message.content.includes('--- Human Agent mode activated ---') || message.content.includes('--- Bot mode activated ---')
              ? 'text-blue-600 bg-blue-50 text-center text-sm'
              : message.sender === 'user'
              ? 'bg-gray-100'
              : message.sender === 'staff'
              ? 'bg-blue-50'
              : 'bg-white border'
          } ${message.className || ''}`}
        >
          {message.content}
        </div>
      ))}
    </div>
  );
}