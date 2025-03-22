'use client';

import { useState, useEffect, useRef } from 'react';
import { ApiService, ChatMessage, ChatSession } from '../../services/api';
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
  const [socketStatus, setSocketStatus] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected');
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
        id: `${msg.timestamp}-${msg.role}-${msg.content.substring(0, 20)}`,
        content: msg.content,
        sender: mapRoleToSender(msg.role),
        timestamp: new Date(msg.timestamp)
      }));

      uiMessages.sort((a: UIMessage, b: UIMessage) => a.timestamp.getTime() - b.timestamp.getTime());
      
      // Use a Map to ensure uniqueness by content+sender+approximate time
      const uniqueMessages = new Map();
      
      for (const msg of uiMessages) {
        // Create a signature that combines content, sender, and approximate time (rounded to nearest 10 seconds)
        const timeWindow = Math.floor(msg.timestamp.getTime() / 10000) * 10000;
        const signature = `${msg.content}|${msg.sender}|${timeWindow}`;
        
        // Only keep the most recent message for each signature
        uniqueMessages.set(signature, msg);
      }
      
      setMessages(Array.from(uniqueMessages.values()));
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
    setSocketStatus('disconnected');
  }, [selectedSession.session_id]);

  // Set up WebSocket connection
  useEffect(() => {
    console.log('StaffChat: WebSocket setup effect running, loading:', loading, 'session ID:', selectedSession.session_id);
    if (loading || !selectedSession.session_id) {
      console.log('Not setting up WebSocket - still loading or no session ID');
      return;
    }
    
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // const wsUrl = `${wsProtocol}//${window.location.host}/ws/chat/${selectedSession.session_id}/staff`;
    const wsUrl = `${wsProtocol}//localhost:8000/ws/chat/${selectedSession.session_id}/staff`;
    
    console.log('Attempting to connect WebSocket to:', wsUrl);
    setSocketStatus('connecting');
    
    const newSocket = new WebSocket(wsUrl);
    
    newSocket.onopen = () => {
      console.log('WebSocket connected successfully for staff view!');
      setSocketStatus('connected');
    };
    
    newSocket.onmessage = (event) => {
      console.log('Staff WebSocket message received:', event.data);
      
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'new_message') {
          console.log('Processing new message from WebSocket:', data.message);
          const newMessage: UIMessage = {
            // Create a more stable ID that combines timestamp, role and content
            id: `${data.message.timestamp}-${data.message.role}-${data.message.content.substring(0, 20)}`,
            content: data.message.content,
            sender: mapRoleToSender(data.message.role),
            timestamp: new Date(data.message.timestamp)
          };
          
          setMessages(prev => {
            // Enhanced duplicate detection
            const isDuplicate = prev.some(msg => {
              // Check content AND sender type for a more precise duplicate check
              const contentMatch = msg.content === newMessage.content;
              const senderMatch = msg.sender === newMessage.sender;
              // Use a 15-second window to catch duplicates from different sources
              const timeClose = Math.abs(
                new Date(msg.timestamp).getTime() - 
                new Date(newMessage.timestamp).getTime()
              ) < 15000; // 15 seconds window
              
              return contentMatch && senderMatch && timeClose;
            });
            
            if (isDuplicate) {
              console.log('Duplicate message detected, not adding to UI');
              return prev;
            }
            
            const updatedMessages = [...prev, newMessage];
            updatedMessages.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
            return updatedMessages;
          });
        } else if (data.type === 'history') {
          console.log('Processing history update from WebSocket:', data.messages.length, 'messages');
          
          // Use setMessages with a callback to ensure we're working with the latest state
          setMessages(prevMessages => {
            // Handle full history update
            const historyMessages = data.messages.map((msg: any) => ({
              id: `${msg.timestamp}-${msg.role}-${msg.content.substring(0, 20)}`,
              content: msg.content,
              sender: mapRoleToSender(msg.role),
              timestamp: new Date(msg.timestamp)
            }));
  
            // Apply the same deduplication strategy as in loadChatHistory
            const uniqueMessages = new Map();
            
            // First add all existing messages to ensure we don't lose anything
            prevMessages.forEach(msg => {
              const timeWindow = Math.floor(msg.timestamp.getTime() / 10000) * 10000;
              const signature = `${msg.content}|${msg.sender}|${timeWindow}`;
              uniqueMessages.set(signature, msg);
            });
            
            // Then add new messages from history update, possibly overwriting older duplicates
            historyMessages.forEach(msg => {
              const timeWindow = Math.floor(msg.timestamp.getTime() / 10000) * 10000;
              const signature = `${msg.content}|${msg.sender}|${timeWindow}`;
              uniqueMessages.set(signature, msg);
            });
            
            // Convert back to array and sort
            const combinedMessages = Array.from(uniqueMessages.values());
            combinedMessages.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
            
            return combinedMessages;
          });
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
      setSocketStatus('disconnected');
      // Try to reconnect after a delay if this wasn't a clean close
      if (event.code !== 1000) { // 1000 = normal closure
        setTimeout(() => {
          console.log('Attempting to reconnect WebSocket...');
          setSocket(null); // This will trigger useEffect to run again
        }, 5000);
      }
    };
    
    newSocket.onerror = (error) => {
      console.error('Staff WebSocket error:', error);
      setSocketStatus('disconnected');
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
      
      // Create staff message object
      const staffMessage: UIMessage = {
        id: Date.now().toString(),
        content,
        sender: 'staff',
        timestamp: new Date(),
      };

      // WebSocket approach. Check if WebSocket is connected
      if (socket && socket.readyState === WebSocket.OPEN) {
        console.log('Sending via WebSocket');
        
        // Add the message to UI immediately for responsiveness
        setMessages(prev => {
          const updatedMessages = [...prev, staffMessage];
          updatedMessages.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
          return updatedMessages;
        });
        
        socket.send(JSON.stringify({
          type: "message",
          content: content,
          customer_id: selectedSession.customer_id,
          // Add a client_message_id to help with duplicate detection
          client_message_id: staffMessage.id
        }));
        
        console.log('Message sent via WebSocket');
        return; // Exit early - no need to call API
      }
      
      // API fallback approach - only runs if WebSocket isn't available
      console.log('WebSocket unavailable, falling back to API');
      
      // Add message to UI before API call for responsiveness
      setMessages(prev => {
        const updatedMessages = [...prev, staffMessage];
        updatedMessages.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
        return updatedMessages;
      });
      
      // Send via API
      await ApiService.sendStaffMessage(
        content, 
        selectedSession.session_id, 
        selectedSession.customer_id
      );
      
      console.log('Message sent successfully via API');
    } catch (err) {
      console.error('Error sending staff message:', err);
      
      // Add error message to UI
      const errorMessage: UIMessage = {
        id: `${Date.now()}-error`,
        content: 'Failed to send message. Please try again.',
        sender: 'system',
        timestamp: new Date()
      };
      
      setMessages(prev => {
        const updatedMessages = [...prev, errorMessage];
        updatedMessages.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
        return updatedMessages;
      });
    }
  };

  // Handle taking over the conversation via WebSocket
  const handleTakeOver = async () => {
    try {
      console.log('Taking over conversation');
      
      // Check if WebSocket is connected
      if (socket && socket.readyState === WebSocket.OPEN) {
        // Send takeover command via WebSocket
        socket.send(JSON.stringify({
          type: "command",
          action: "takeover",
          session_id: selectedSession.session_id,
          customer_id: selectedSession.customer_id
        }));
        
        console.log('Takeover command sent via WebSocket');
        // Don't add system message here - will come from server via WebSocket
      } else {
        // Fallback to API if WebSocket is not available
        console.log('WebSocket not available, using API fallback');
        await ApiService.takeOverSession(
          selectedSession.session_id, 
          selectedSession.customer_id
        );
        
        // Add system message to UI
        const takeoverMessage: UIMessage = {
          id: `${Date.now()}-takeover`,
          content: '--- Human Agent mode activated ---',
          sender: 'system',
          timestamp: new Date()
        };
        
        setMessages(prev => {
          const updatedMessages = [...prev, takeoverMessage];
          updatedMessages.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
          return updatedMessages;
        });
      }
      
      // Update UI state
      setIsHumanMode(true);
      
    } catch (err) {
      console.error('Error taking over session:', err);
      
      // Add error message to UI
      const errorMessage: UIMessage = {
        id: `${Date.now()}-error`,
        content: 'Failed to take over conversation. Please try again.',
        sender: 'system',
        timestamp: new Date()
      };
      
      setMessages(prev => {
        const updatedMessages = [...prev, errorMessage];
        updatedMessages.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
        return updatedMessages;
      });
    }
  };

  // Handle transferring back to bot, via WebSocket
  const handleTransferToBot = async () => {
    try {
      console.log('Transferring to bot');
      
      // Check if WebSocket is connected
      if (socket && socket.readyState === WebSocket.OPEN) {
        // Send transfer command via WebSocket
        socket.send(JSON.stringify({
          type: "command",
          action: "transfer_to_bot",
          session_id: selectedSession.session_id,
          customer_id: selectedSession.customer_id
        }));
        
        console.log('Transfer command sent via WebSocket');
        // Don't add system message here - will come from server via WebSocket
      } else {
        // Fallback to API if WebSocket is not available
        console.log('WebSocket not available, using API fallback');
        await ApiService.transferToBot(
          selectedSession.session_id, 
          selectedSession.customer_id
        );
        
        // Add system message to UI
        const transferMessage: UIMessage = {
          id: `${Date.now()}-transfer`,
          content: '--- Bot mode activated ---',
          sender: 'system',
          timestamp: new Date()
        };
        
        setMessages(prev => {
          const updatedMessages = [...prev, transferMessage];
          updatedMessages.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
          return updatedMessages;
        });
      }
      
      // Update UI state
      setIsHumanMode(false);
      
    } catch (err) {
      console.error('Error transferring to bot:', err);
      
      // Add error message to UI
      const errorMessage: UIMessage = {
        id: `${Date.now()}-error`,
        content: 'Failed to transfer to bot. Please try again.',
        sender: 'system',
        timestamp: new Date()
      };
      
      setMessages(prev => {
        const updatedMessages = [...prev, errorMessage];
        updatedMessages.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
        return updatedMessages;
      });
    }
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
            WebSocket: {
              socketStatus === 'connected' ? 'Connected' : 
              socketStatus === 'connecting' ? 'Connecting...' : 
              'Disconnected'
            }
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
            onClick={loadChatHistory}
            size="sm"
            variant="ghost"
            className="w-8 h-8 p-0"
          >
            <RefreshCw className="w-4 h-4" />
          </Button>
        </div>
      </div>
      
      <div className="flex-1 overflow-auto p-4">
        {messages.map(message => {
          // Format date and time
          const messageDate = new Date(message.timestamp);
          const formattedDate = messageDate.toLocaleDateString();
          const formattedTime = messageDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
          
          return (
            <div 
              key={message.id}
              style={{
                padding: '10px',
                margin: '8px 0',
                borderRadius: '8px',
                backgroundColor: message.sender === 'user' ? '#e6f7ff' : '#f0f0f0',
                border: '2px solid #d9d9d9',
                marginLeft: message.sender === 'user' ? 'auto' : '0',
                marginRight: message.sender === 'user' ? '0' : 'auto',
                maxWidth: '80%'
              }}
            >
              <div style={{ fontSize: '0.75rem', color: '#666', marginBottom: '4px' }}>
                <strong>
                  {message.sender === 'user' ? 'Customer' : 
                  message.sender === 'bot' ? 'Bot' : 
                  message.sender === 'staff' ? 'Support Agent' : 'System'}
                </strong> • {formattedDate} {formattedTime}
              </div>
              <div>{message.content}</div>
            </div>
          );
        })}
        
        <div ref={messagesEndRef} />
      </div>
      <div className="p-4 border-t">
        <MessageInput 
          onSendMessage={handleSendMessage} 
          isStaffMode={true} 
          placeholder="Type as Support agent..."
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