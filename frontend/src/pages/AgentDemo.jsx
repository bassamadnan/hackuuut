import React, { useState, useRef, useEffect } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import ReactMarkdown from 'react-markdown';

const AgentDemo = () => {
  const [messages, setMessages] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [iterations, setIterations] = useState(0);
  const [error, setError] = useState(null);
  const [agents, setAgents] = useState({
    ec2_agent: { color: 'bg-blue-500', icon: '💻', responses: 0 },
    billing_agent: { color: 'bg-green-500', icon: '💲', responses: 0 },
    security_agent: { color: 'bg-red-500', icon: '🔒', responses: 0 },
    logs_agent: { color: 'bg-purple-500', icon: '📊', responses: 0 },
  });
  
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const startDemo = async () => {
    if (isRunning) return;
    
    setIsRunning(true);
    setMessages([]);
    setIterations(0);
    setSessionId(null);
    setError(null);
    setAgents(prevAgents => {
      const resetAgents = {...prevAgents};
      Object.keys(resetAgents).forEach(key => {
        resetAgents[key].responses = 0;
      });
      return resetAgents;
    });
    
    try {
      // Add initial system message
      setMessages([{
        role: 'system',
        content: '# Starting AWS Cost Spike Investigation\n\nInitiating concurrent multi-agent analysis to investigate the AWS cost spike. Multiple specialized agents will analyze this issue concurrently across several iterations.'
      }]);
      
      // Add user query
      const userMessage = `
URGENT INVESTIGATION NEEDED: We've noticed a significant spike in our AWS costs this month, 
almost double what we normally spend. Our month-to-date bill is already over $4,000 
when we normally spend about $2,000 for the entire month.

Can you help investigate what's causing this cost increase? We need a thorough multi-phase analysis:

1. First identify what services or resources are causing the unusual costs and if there's 
   any suspicious activity or potential security issues

2. Then provide a detailed analysis of the root cause and potential impact to our business

3. Finally recommend specific actions we should take immediately and preventive measures 
   for the future

Our team is really concerned about this as we're a small startup and this could impact our runway.
Please be thorough and investigate this step-by-step.
      `;
      
      setMessages(prev => [...prev, {
        role: 'user',
        content: userMessage,
        timestamp: new Date().toISOString()
      }]);
      
      // Start the orchestration process
      const response = await fetch('/api/agent_demo/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: userMessage }),
      });
      
      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }
      
      const data = await response.json();
      setSessionId(data.session_id);
      
      // Begin polling for updates
      pollForUpdates(data.session_id);
      
    } catch (err) {
      console.error('Error starting demo:', err);
      setError(`Failed to start demo: ${err.message}`);
      setIsRunning(false);
    }
  };
  
  const pollForUpdates = async (threadId) => {
    let isComplete = false;
    
    while (!isComplete) {
      try {
        const response = await fetch(`/api/agent_demo/status?thread_id=${threadId}`);
        
        if (!response.ok) {
          throw new Error(`Server error: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Update state with new messages
        if (data.messages && data.messages.length > 0) {
          setMessages(prev => {
            // Find messages we don't already have
            const newMessages = data.messages.filter(
              newMsg => !prev.some(
                existingMsg => existingMsg.id === newMsg.id
              )
            );
            
            // Update agent response counts
            newMessages.forEach(msg => {
              if (msg.agent && agents[msg.agent]) {
                setAgents(prev => ({
                  ...prev,
                  [msg.agent]: {
                    ...prev[msg.agent],
                    responses: prev[msg.agent].responses + 1
                  }
                }));
              }
            });
            
            return [...prev, ...newMessages];
          });
        }
        
        // Update iteration count
        if (data.iterations > iterations) {
          setIterations(data.iterations);
        }
        
        // Check if process is complete
        if (data.status === 'complete') {
          isComplete = true;
          setIsRunning(false);
        } else {
          // Wait before polling again
          await new Promise(resolve => setTimeout(resolve, 2000));
        }
        
      } catch (err) {
        console.error('Error polling for updates:', err);
        setError(`Failed to get updates: ${err.message}`);
        isComplete = true;
        setIsRunning(false);
      }
    }
  };

  // Custom renderer for code blocks in markdown
  const components = {
    code({ node, inline, className, children, ...props }) {
      const match = /language-(\w+)/.exec(className || '');
      return !inline && match ? (
        <SyntaxHighlighter
          style={vscDarkPlus}
          language={match[1]}
          PreTag="div"
          {...props}
        >
          {String(children).replace(/\n$/, '')}
        </SyntaxHighlighter>
      ) : (
        <code className={className} {...props}>
          {children}
        </code>
      );
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gradient-to-b from-base-300 to-base-200">
      {/* Header */}
      <div className="p-4 bg-base-100 shadow-md">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-2xl font-bold">Multi-Agent Orchestration Demo</h1>
          <p className="text-sm opacity-75">This demo shows how multiple AI agents can work together to solve complex problems.</p>
        </div>
      </div>
      
      {/* Main content */}
      <div className="flex-1 overflow-hidden grid grid-cols-1 lg:grid-cols-4 gap-4 p-4">
        {/* Agent status sidebar */}
        <div className="bg-base-100 rounded-box shadow-lg p-4 hidden lg:block">
          <h2 className="font-bold text-lg mb-4">Agent Status</h2>
          
          <div className="space-y-4">
            <div className="stats stats-vertical shadow">
              <div className="stat">
                <div className="stat-title">Session</div>
                <div className="stat-value text-sm truncate">{sessionId || 'Not started'}</div>
              </div>
              
              <div className="stat">
                <div className="stat-title">Status</div>
                <div className="stat-value text-primary">
                  {isRunning ? (
                    <span className="flex items-center">
                      <span className="loading loading-spinner loading-sm mr-2"></span>
                      Running
                    </span>
                  ) : 'Ready'}
                </div>
              </div>
              
              <div className="stat">
                <div className="stat-title">Iterations</div>
                <div className="stat-value">{iterations}</div>
              </div>
            </div>
            
            <div className="divider">Agents</div>
            
            {Object.entries(agents).map(([name, agent]) => (
              <div key={name} className="flex items-center p-2 rounded-lg bg-base-200 mb-2">
                <div className={`avatar placeholder mr-2`}>
                  <div className={`${agent.color} text-white rounded-full w-8`}>
                    <span>{agent.icon}</span>
                  </div>
                </div>
                <div className="flex-1">
                  <div className="font-medium">{name.replace('_', ' ')}</div>
                  <div className="text-xs opacity-70">{agent.responses} responses</div>
                </div>
                <div className="badge badge-accent badge-sm">{isRunning && Math.random() > 0.6 ? 'active' : 'idle'}</div>
              </div>
            ))}
            
            <button 
              className={`btn btn-primary w-full mt-4 ${isRunning ? 'btn-disabled' : ''}`}
              onClick={startDemo}
              disabled={isRunning}
            >
              {isRunning ? (
                <>
                  <span className="loading loading-spinner"></span>
                  Running...
                </>
              ) : 'Start Demo'}
            </button>
          </div>
        </div>
        
        {/* Message thread */}
        <div className="bg-base-100 rounded-box shadow-lg p-4 overflow-y-auto col-span-1 lg:col-span-3 relative">
          {/* Mobile start button */}
          <div className="lg:hidden mb-4">
            <button 
              className={`btn btn-primary w-full ${isRunning ? 'btn-disabled' : ''}`}
              onClick={startDemo}
              disabled={isRunning}
            >
              {isRunning ? (
                <>
                  <span className="loading loading-spinner"></span>
                  Running...
                </>
              ) : 'Start Demo'}
            </button>
            
            <div className="stats shadow w-full mt-2">
              <div className="stat">
                <div className="stat-title">Iterations</div>
                <div className="stat-value text-lg">{iterations}</div>
              </div>
              <div className="stat">
                <div className="stat-title">Status</div>
                <div className="stat-value text-lg">{isRunning ? 'Running' : 'Ready'}</div>
              </div>
            </div>
          </div>
          
          {/* Messages */}
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center text-gray-500 py-12">
              <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-10 h-10 text-primary">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <p className="text-xl font-medium">AWS Multi-Agent Demo</p>
              <p className="text-sm mt-2 max-w-md">Click "Start Demo" to see multiple AI agents work together to investigate and solve an AWS cost spike issue.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((message, index) => {
                // Special iteration separator
                if (message.type === 'iteration') {
                  return (
                    <div key={`iter-${index}`} className="flex justify-center my-6">
                      <div className="badge badge-lg badge-accent gap-2">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                        </svg>
                        Iteration {message.iteration}
                      </div>
                    </div>
                  );
                }
                
                // Normal message
                const isUser = message.role === 'user';
                const isSystem = message.role === 'system';
                const agentData = !isUser && !isSystem && message.agent ? agents[message.agent] : null;
                
                return (
                  <div key={index} className={`chat ${isUser ? 'chat-end' : 'chat-start'}`}>
                    <div className="chat-image avatar">
                      <div className="w-10 rounded-full">
                        {isUser ? (
                          <div className="bg-primary text-primary-content rounded-full w-full h-full flex items-center justify-center">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                            </svg>
                          </div>
                        ) : isSystem ? (
                          <div className="bg-accent text-accent-content rounded-full w-full h-full flex items-center justify-center">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                            </svg>
                          </div>
                        ) : (
                          <div className={`${agentData?.color || 'bg-secondary'} text-white rounded-full w-full h-full flex items-center justify-center`}>
                            <span>{agentData?.icon || '🤖'}</span>
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="chat-header">
                      {isUser ? 'You' : isSystem ? 'System' : message.agent || 'Assistant'}
                      <time className="text-xs opacity-50 ml-1">{new Date(message.timestamp || Date.now()).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</time>
                    </div>
                    <div className={`chat-bubble ${isUser ? 'chat-bubble-primary' : isSystem ? 'chat-bubble-accent' : 'chat-bubble-secondary'} shadow-md max-w-4xl`}>
                      <ReactMarkdown components={components}>
                        {message.content}
                      </ReactMarkdown>
                    </div>
                    {message.iteration && (
                      <div className="chat-footer opacity-70">
                        <span className="badge badge-sm">Iteration {message.iteration}</span>
                      </div>
                    )}
                  </div>
                );
              })}
              
              {/* Loading indicator */}
              {isRunning && (
                <div className="chat chat-start">
                  <div className="chat-image avatar">
                    <div className="w-10 rounded-full">
                      <div className="bg-info text-info-content rounded-full w-full h-full flex items-center justify-center">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                        </svg>
                      </div>
                    </div>
                  </div>
                  <div className="chat-bubble chat-bubble-info shadow-md">
                    <div className="flex items-center space-x-2">
                      <span className="loading loading-dots loading-sm"></span>
                      <span>Multiple agents processing...</span>
                    </div>
                  </div>
                </div>
              )}
              
              {/* Error message */}
              {error && (
                <div className="chat chat-start">
                  <div className="chat-image avatar">
                    <div className="w-10 rounded-full">
                      <div className="bg-error text-error-content rounded-full w-full h-full flex items-center justify-center">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-6 h-6">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                        </svg>
                      </div>
                    </div>
                  </div>
                  <div className="chat-bubble chat-bubble-error shadow-md">
                    {error}
                  </div>
                </div>
              )}
            </div>
          )}
          
          {/* Invisible element for auto-scrolling */}
          <div ref={messagesEndRef} />
        </div>
      </div>
    </div>
  );
};

export default AgentDemo; 