'use client';

import { useState, useEffect, useRef } from 'react';
import { ApiService, ChatMessage, ChatSession } from '../../services/api';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import { Button } from '../ui/button';
import { User, Bot, RefreshCw } from 'lucide-react';

interface StaffChatProps {
  selectedSession: ChatSession;
  activeSessions: ChatSession[];
}

interface UIMessage {
  id: string;
  content: string;
  sender: 'user' | 'bot' | 'staff' | 'system';
  timestamp: Date;
}

export default function StaffChat({ selectedSession}: StaffChatProps) {
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isHumanMode, setIsHumanMode] = useState(selectedSession.current_agent === 'HUMAN');
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // Scroll to bottom when messages change
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Load chat history
  const loadChatHistory = async () => {
    try {
      setLoading(true);
      console.log('Loading chat history for session:', selectedSession.session_id);
      const history = await ApiService.getChatHistory(
        selectedSession.session_id, 
        selectedSession.customer_id
      );
      
      console.log('Received chat history:', history.length, 'messages');
      
      // Map backend messages to UI format
      const uiMessages = history.map((msg: ChatMessage) => ({
        id: `${msg.timestamp}-${Math.random()}`,
        content: msg.content,
        sender: mapRoleToSender(msg.role),
        timestamp: new Date(msg.timestamp)
      }));
      
      setMessages(uiMessages);
      setLoading(false);
    } catch (err) {
      console.error('Error loading chat history:', err);
      setError('Could not load chat history');
      setLoading(false);
    }
  };

  // Load initial chat history
  useEffect(() => {
    loadChatHistory();
    // Update human mode based on session state
    setIsHumanMode(selectedSession.current_agent === 'HUMAN');
    
    // Close existing WebSocket if there is one
    if (socket && socket.readyState === WebSocket.OPEN) {
      console.log('Closing existing WebSocket connection');
      socket.close();
    }
    
    setSocket(null); // This will trigger the WebSocket setup effect
  }, [selectedSession.session_id]);

  // Set up WebSocket connection
  useEffect(() => {
    console.log('CustomerChat: WebSocket setup effect running');
    console.log('Loading state:', loading);
    console.log('SessionId from props:', selectedSession.session_id);
    console.log('StaffChat: WebSocket setup effect running, loading:', loading, 'session ID:', selectedSession.session_id);
    if (loading || !selectedSession.session_id) {
      console.log('Not setting up WebSocket - still loading or no session ID');
      return;
    }
    
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // const wsUrl = `${wsProtocol}//${window.location.host}/ws/chat/${selectedSession.session_id}/staff`;
    const wsUrl = `${wsProtocol}//localhost:8000/ws/chat/${selectedSession.session_id}/staff`;
    
    console.log('Attempting to connect WebSocket to:', wsUrl);
    
    const newSocket = new WebSocket(wsUrl);
    
    newSocket.onopen = () => {
      console.log('WebSocket connected successfully for staff view!');
    };
    
    newSocket.onmessage = (event) => {
      console.log('Staff WebSocket message received:', event.data);
      
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'new_message') {
          console.log('Processing new message from WebSocket:', data.message);
          const newMessage: UIMessage = {
            id: `${data.message.timestamp}-${Math.random()}`,
            content: data.message.content,
            sender: mapRoleToSender(data.message.role),
            timestamp: new Date(data.message.timestamp)
          };
          
          setMessages(prev => [...prev, newMessage]);
        } else if (data.type === 'history') {
          console.log('Processing history update from WebSocket:', data.messages.length, 'messages');
          // Handle full history update
          const historyMessages = data.messages.map((msg: any) => ({
            id: `${msg.timestamp}-${Math.random()}`,
            content: msg.content,
            sender: mapRoleToSender(msg.role),
            timestamp: new Date(msg.timestamp)
          }));
          
          setMessages(historyMessages);
        } else if (data.type === 'agent_change') {
          console.log('Agent changed to:', data.current_agent);
          // Handle agent change notifications
          setIsHumanMode(data.current_agent === 'HUMAN');
        } else {
          console.log('Unknown message type:', data.type);
        }
      } catch (err) {
        console.error('Error processing WebSocket message:', err, event.data);
      }
    };
    
    newSocket.onclose = (event) => {
      console.log('Staff WebSocket disconnected:', event.code, event.reason);
      // Try to reconnect after a delay
      setTimeout(() => {
        if (newSocket.readyState === WebSocket.CLOSED) {
          console.log('WebSocket still closed after timeout, will reset socket state');
          setSocket(null); // This will trigger useEffect to run again
        }
      }, 5000);
    };
    
    newSocket.onerror = (error) => {
      console.error('Staff WebSocket error:', error);
    };
    
    setSocket(newSocket);
    
    // Clean up on unmount
    return () => {
      console.log('Cleaning up WebSocket connection');
      if (newSocket.readyState === WebSocket.OPEN || newSocket.readyState === WebSocket.CONNECTING) {
        newSocket.close();
      }
    };
  }, [selectedSession.session_id, loading]);

  // Poll for new messages (as fallback if WebSocket fails)
  useEffect(() => {
    // Only fall back to polling if WebSocket isn't connected
    if (socket && socket.readyState === WebSocket.OPEN) {
      console.log('WebSocket connected, skipping polling');
      return;
    }
    
    console.log('Setting up polling fallback (every 5s)');
    const pollInterval = setInterval(async () => {
      try {
        const history = await ApiService.getChatHistory(
          selectedSession.session_id, 
          selectedSession.customer_id
        );
        
        // Only update if we have more messages than current state
        if (history.length > messages.length) {
          console.log('Polling found new messages:', history.length - messages.length);
          const uiMessages = history.map((msg: ChatMessage) => ({
            id: `${msg.timestamp}-${Math.random()}`,
            content: msg.content,
            sender: mapRoleToSender(msg.role),
            timestamp: new Date(msg.timestamp)
          }));
          
          setMessages(uiMessages);
        }
      } catch (err) {
        console.error('Error polling chat history:', err);
      }
    }, 5000); // Poll every 5 seconds
    
    return () => {
      console.log('Clearing polling interval');
      clearInterval(pollInterval);
    };
  }, [selectedSession, messages.length, socket]);

  // Scroll to bottom whenever messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Helper to map backend roles to UI sender types
  const mapRoleToSender = (role: string): 'user' | 'bot' | 'staff' | 'system' => {
    role = role?.toUpperCase() || '';
    
    switch (role) {
      case 'CUSTOMER':
      case 'USER':
        return 'user';
      case 'BOT':
        return 'bot';
      case 'HUMAN_AGENT':
        return 'staff';
      case 'SYSTEM':
        return 'system';
      default:
        console.log('Unknown role type:', role);
        return 'system';
    }
  };

  // Handle staff sending a message
  const handleSendMessage = async (content: string) => {
    if (!content.trim()) return;

    try {
      // Ensure we're in human mode first
      if (!isHumanMode) {
        console.log('Not in human mode, taking over...');
        await handleTakeOver();
      }
      
      console.log('Sending staff message:', content);
      
      // Add staff message to UI immediately for responsiveness
      const staffMessage: UIMessage = {
        id: Date.now().toString(),
        content,
        sender: 'staff',
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, staffMessage]);

      // Add after adding staff message to UI (around line 287)
      if (socket && socket.readyState === WebSocket.OPEN) {
        console.log('Sending via WebSocket');
        socket.send(JSON.stringify({
          type: "message",
          content: content,
          customer_id: selectedSession.customer_id
        }));
        console.log('Message sent via WebSocket');
        return; // Exit early - no need to call API
      }

      console.log('WebSocket unavailable, falling back to API');
      await ApiService.sendStaffMessage(
        content, 
        selectedSession.session_id, 
        selectedSession.customer_id
      );
      
      console.log('Message sent successfully');
    } catch (err) {
      console.error('Error sending staff message:', err);
      
      // Add error message to UI
      const errorMessage: UIMessage = {
        id: `${Date.now()}-error`,
        content: 'Failed to send message. Please try again.',
        sender: 'system',
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, errorMessage]);
    }
  };

  // Handle taking over the conversation
  const handleTakeOver = async () => {
    try {
      console.log('Taking over conversation');
      await ApiService.takeOverSession(
        selectedSession.session_id, 
        selectedSession.customer_id
      );
      
      setIsHumanMode(true);
      
      // Add system message to UI
      const takeoverMessage: UIMessage = {
        id: `${Date.now()}-takeover`,
        content: '--- Human Agent mode activated ---',
        sender: 'system',
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, takeoverMessage]);
      console.log('Takeover successful');
    } catch (err) {
      console.error('Error taking over session:', err);
      
      // Add error message to UI
      const errorMessage: UIMessage = {
        id: `${Date.now()}-error`,
        content: 'Failed to take over conversation. Please try again.',
        sender: 'system',
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, errorMessage]);
    }
  };

  // Handle transferring back to bot
  const handleTransferToBot = async () => {
    try {
      console.log('Transferring to bot');
      await ApiService.transferToBot(
        selectedSession.session_id, 
        selectedSession.customer_id
      );
      
      setIsHumanMode(false);
      
      // Add system message to UI
      const transferMessage: UIMessage = {
        id: `${Date.now()}-transfer`,
        content: '--- Bot mode activated ---',
        sender: 'system',
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, transferMessage]);
      console.log('Transfer to bot successful');
    } catch (err) {
      console.error('Error transferring to bot:', err);
      
      // Add error message to UI
      const errorMessage: UIMessage = {
        id: `${Date.now()}-error`,
        content: 'Failed to transfer to bot. Please try again.',
        sender: 'system',
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, errorMessage]);
    }
  };

  // Handle refreshing the chat
  const handleRefresh = () => {
    console.log('Manually refreshing chat');
    loadChatHistory();
  };

  if (loading) {
    return <div className="flex justify-center items-center h-full">Loading...</div>;
  }

  if (error) {
    return <div className="flex justify-center items-center h-full text-red-500">{error}</div>;
  }

  return (
    <div className="flex flex-col h-[calc(100%-3.5rem)]">
      <div className="p-2 border-b bg-gray-50 flex justify-between items-center">
        <div>
          <div className="font-medium">Customer: {selectedSession.customer_id}</div>
          <div className="text-xs text-gray-500">
            Session: {selectedSession.session_id.substring(0, 8)}... | 
            Messages: {selectedSession.message_count} | 
            WebSocket: {socket ? (socket.readyState === WebSocket.OPEN ? 'Connected' : 'Connecting...') : 'Disconnected'}
          </div>
        </div>
        <div className="flex gap-2">
          {isHumanMode ? (
            <Button 
              onClick={handleTransferToBot}
              size="sm"
              variant="outline"
              className="flex items-center gap-1"
            >
              <Bot className="w-4 h-4" />
              <span>Transfer to Bot</span>
            </Button>
          ) : (
            <Button 
              onClick={handleTakeOver}
              size="sm"
              variant="default"
              className="flex items-center gap-1 bg-blue-500 hover:bg-blue-600"
            >
              <User className="w-4 h-4" />
              <span>Take Over</span>
            </Button>
          )}
          <Button
            onClick={handleRefresh}
            size="sm"
            variant="ghost"
            className="w-8 h-8 p-0"
          >
            <RefreshCw className="w-4 h-4" />
          </Button>
        </div>
      </div>
      
      <div className="flex-1 overflow-auto p-4">
        <MessageList messages={messages} />
        <div ref={messagesEndRef} />
      </div>
      
      <div className="p-4 border-t">
        <MessageInput 
          onSendMessage={handleSendMessage} 
          isStaffMode={true} 
          placeholder="Type as support agent..."
          isDisabled={!isHumanMode}
        />
        {!isHumanMode && (
          <div className="text-xs text-center mt-2 text-gray-500">
            Click 'Take Over' to respond as a human agent
          </div>
        )}
      </div>
    </div>
  );
}