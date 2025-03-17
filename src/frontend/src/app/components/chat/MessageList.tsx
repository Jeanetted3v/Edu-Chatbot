'use client';

import React from 'react';
import { format } from 'date-fns';

interface Message {
  id: string;
  content: string;
  sender: 'user' | 'bot' | 'staff' | 'system';
  timestamp: Date;
  className?: string;
}

interface MessageListProps {
  messages: Message[];
}

export default function MessageList({ messages }: MessageListProps) {
  console.log('MessageList rendering with', messages.length, 'messages'); // Debug log

  // Helper function to safely format dates
  const safeFormatDate = (timestamp: any, formatString: string) => {
    try {
      if (!timestamp) return format(new Date(), formatString);
      const date = new Date(timestamp);
      // Check if date is valid
      if (isNaN(date.getTime())) return format(new Date(), formatString);
      return format(date, formatString);
    } catch (e) {
      console.error('Error formatting date:', e, 'timestamp:', timestamp);
      return format(new Date(), formatString);
    }
  };

  // Group messages by date for better readability
  const groupedMessages = messages.reduce((groups: Record<string, Message[]>, message) => {
    const date = safeFormatDate(message.timestamp, 'yyyy-MM-dd');
    if (!groups[date]) {
      groups[date] = [];
    }
    groups[date].push(message);
    return groups;
  }, {});

  // Format a timestamp
  const formatTime = (timestamp: Date) => {
    return safeFormatDate(timestamp, 'HH:mm');
  };

  // Get message class based on sender
  const getMessageClass = (message: Message) => {
    // System messages (agent transfers, etc.)
    if (message.sender === 'system' || 
        message.content.includes('--- Human Agent mode activated ---') || 
        message.content.includes('--- Bot mode activated ---')) {
      return 'text-blue-600 bg-blue-50 text-center text-sm py-1 my-2';
    }
    
    // User messages (customer)
    if (message.sender === 'user') {
      return 'bg-gray-100 ml-12';
    }
    
    // Staff messages (human agents)
    if (message.sender === 'staff') {
      return 'bg-blue-50 mr-12';
    }
    
    // Bot messages
    return 'bg-white border mr-12';
  };

  return (
    <div className="space-y-4">
      {/* Debug info */}
      <div className="text-xs text-gray-500 bg-yellow-50 p-1 mb-2">
        Total messages: {messages.length} | Groups: {Object.keys(groupedMessages).length}
      </div>
      
      {Object.keys(groupedMessages).map(date => (
        <div key={date}>
          <div className="text-center text-xs text-gray-500 my-2">
            {safeFormatDate(date, 'MMMM d, yyyy')}
          </div>
          
          {groupedMessages[date].map((message) => (
            <div
              key={message.id}
              className={`p-3 rounded-lg mb-2 ${getMessageClass(message)} ${message.className || ''}`}
              style={{ border: '1px solid #e2e8f0' }} // Add visible border for debugging
            >
              {/* Render system messages differently */}
              {message.sender === 'system' ? (
                <div>{message.content}</div>
              ) : (
                <>
                  {/* Show who sent the message */}
                  <div className="text-xs text-gray-500 mb-1">
                    {message.sender === 'user' && 'Customer'}
                    {message.sender === 'bot' && 'Bot'}
                    {message.sender === 'staff' && 'Support Agent'}
                    {' • '}
                    {formatTime(message.timestamp)}
                  </div>
                  
                  {/* Message content */}
                  <div className="whitespace-pre-line">{message.content}</div>
                </>
              )}
            </div>
          ))}
        </div>
      ))}
      
      {messages.length === 0 && (
        <div className="text-center text-gray-500 p-4">
          No messages yet
        </div>
      )}
    </div>
  );
}