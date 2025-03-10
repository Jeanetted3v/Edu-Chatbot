'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/app/components/ui/card";
import MessageList from './MessageList';
import MessageInput from './MessageInput';

interface Message {
  id: string;
  content: string;
  sender: 'user' | 'bot' | 'staff';
  timestamp: Date;
}

export default function ChatContainer() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isHumanAgent, setIsHumanAgent] = useState(false);

  const handleSendMessage = async (content: string) => {
    if (!content.trim()) return;

    const newMessage: Message = {
      id: Date.now().toString(),
      content,
      sender: isHumanAgent ? 'staff' : 'user',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, newMessage]);

    if (!isHumanAgent) {
      setTimeout(() => {
        const botResponse: Message = {
          id: Date.now().toString(),
          content: 'This is a sample bot response.',
          sender: 'bot',
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, botResponse]);
      }, 1000);
    }
  };

  const toggleHumanAgent = () => {
    setIsHumanAgent(!isHumanAgent);
    const newMessage = {
      id: Date.now().toString(),
      content: isHumanAgent 
        ? '--- Bot mode activated ---'
        : '--- Human Agent mode activated ---',
      sender: 'staff',
      timestamp: new Date(),
      className: 'text-blue-600 bg-blue-50'
    };
    setMessages(prev => [...prev, newMessage]);
  };

  return (
    <Card className="w-full h-[calc(100vh-200px)] flex flex-col">
      <CardHeader className="py-2 px-4">
        <CardTitle className="flex justify-end items-center">
          <button
            onClick={toggleHumanAgent}
            className={`px-6 py-1.5 rounded-md text-sm ${
              isHumanAgent 
                ? 'bg-blue-500 text-white hover:bg-blue-600' 
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            } transition-colors duration-200`}
          >
            {isHumanAgent ? 'Human Agent Active' : 'Toggle Human Agent'}
          </button>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 flex gap-4 p-4 h-full">
        <div className="flex flex-col w-full h-full">
          <div className="flex-1 overflow-auto">
            <MessageList messages={messages} />
          </div>
          <div className="mt-4">
            <MessageInput onSendMessage={handleSendMessage} isStaffMode={isHumanAgent} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}