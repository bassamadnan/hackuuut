import React, { useState, useRef, useEffect } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import ReactMarkdown from 'react-markdown';
import '../agent-styles.css';

const AgentDemo = () => {
  const [messages, setMessages] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [iterations, setIterations] = useState(0);
  const [error, setError] = useState(null);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [showSteps, setShowSteps] = useState(false);
  const [iterationAgents, setIterationAgents] = useState({});
  const [agents, setAgents] = useState({
    classifier: { color: 'bg-amber-500', icon: '🧠', responses: 0 },
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

  // Track which agents participated in each iteration
  useEffect(() => {
    const iterationMap = {};
    const classifierSelections = {};
    
    messages.forEach(msg => {
      if (msg.iteration && msg.agent && !msg.type) {
        if (!iterationMap[msg.iteration]) {
          iterationMap[msg.iteration] = new Set();
        }
        iterationMap[msg.iteration].add(msg.agent);
        
        // Track classifier decisions that contain NEXT_STEP or CONTINUE keywords
        if (msg.agent === 'classifier' && (msg.content.includes('NEXT_STEP') || msg.content.includes('CONTINUE'))) {
          classifierSelections[msg.iteration] = msg;
        }
      }
    });
    
    // Convert Sets to Arrays for easier use in rendering
    const formattedMap = {};
    Object.keys(iterationMap).forEach(iteration => {
      formattedMap[iteration] = Array.from(iterationMap[iteration]);
    });
    
    setIterationAgents(formattedMap);
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
    setSelectedAgent(null);
    setShowSteps(false);
    setIterationAgents({});
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
          setShowSteps(true); // Automatically show steps visualization when complete
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

  // Filter messages by selected agent
  const filteredMessages = selectedAgent 
    ? messages.filter(msg => 
        msg.agent === selectedAgent || 
        msg.role === 'user' || 
        msg.type === 'iteration'
      )
    : messages;

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

  // Get agent data by name
  const getAgentData = (agentName) => {
    return agents[agentName] || { 
      color: 'bg-gray-500', 
      icon: '❓', 
      responses: 0 
    };
  };

  // Helper to create step-by-step visual representation
  const renderStepsVisualization = () => {
    const steps = [
      {
        title: "Investigation Initiated",
        description: "Cost spike analysis triggered with specialized agents",
        icon: "📋",
        details: "The classifier agent analyzes the request and distributes tasks to specialized AWS agents."
      },
      {
        title: "Initial Analysis",
        description: "Agents concurrently analyze EC2, billing, security, and logs",
        icon: "🔍",
        details: "Each specialized agent examines their respective AWS domain to identify anomalies."
      },
      {
        title: "Root Cause Identification",
        description: "Security breach identified, unauthorized instance discovered",
        icon: "⚠️",
        details: "Evidence from all agents converges on a security breach involving cryptocurrency mining."
      },
      {
        title: "Remediation Planning",
        description: "Comprehensive action plan developed",
        icon: "🛠️",
        details: "Agents collaborate to develop short and long-term fixes across EC2, IAM, monitoring, and billing."
      },
      {
        title: "Final Recommendations",
        description: "Immediate actions, short-term fixes, and long-term strategy",
        icon: "✅",
        details: "A complete remediation strategy is presented with concrete steps and expected outcomes."
      }
    ];

    return (
      <div className="mt-4">
        {/* Infographic version */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-5 relative overflow-hidden">
          {/* Progress bar */}
          <div className="absolute h-2 bg-base-300 top-14 left-0 right-0 md:top-auto md:bottom-auto md:mt-16 z-0">
            <div 
              className="h-full bg-accent transition-all duration-1000" 
              style={{ width: `${Math.min(100, (iterations / steps.length) * 100)}%` }}
            ></div>
          </div>

          {steps.map((step, index) => {
            const isActive = index < iterations;
            const isCurrentStep = index === iterations - 1;
            const relatedAgents = iterationAgents[index + 1] || [];
            
            return (
              <div key={index} className={`flex flex-col items-center p-4 rounded-lg relative z-10 transition-all duration-500 ${
                isActive ? 'bg-base-200 scale-100' : 'opacity-60 scale-95'
              } ${isCurrentStep ? 'ring-2 ring-accent' : ''}`}>
                {/* Step number bubble */}
                <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-3 text-lg font-bold ${
                  isActive ? 'bg-accent text-accent-content' : 'bg-base-300 text-base-content'
                }`}>
                  {index + 1}
                </div>
                
                {/* Step icon */}
                <div className="text-3xl mb-2">{step.icon}</div>
                
                {/* Title */}
                <h3 className="text-lg font-bold text-center mb-1">{step.title}</h3>
                
                {/* Description */}
                <p className="text-sm text-center mb-3 opacity-80">{step.description}</p>
                
                {/* Agents involved */}
                {isActive && relatedAgents.length > 0 && (
                  <div className="mt-auto w-full">
                    <div className="text-xs uppercase opacity-70 text-center mb-1">Agents Involved</div>
                    <div className="flex flex-wrap justify-center gap-1">
                      {relatedAgents.map(agentName => {
                        const agent = getAgentData(agentName);
                        return (
                          <div 
                            key={agentName} 
                            className={`badge ${agent.color.replace('bg-', 'badge-')} badge-sm cursor-pointer`}
                            onClick={() => setSelectedAgent(selectedAgent === agentName ? null : agentName)}
                          >
                            <span>{agent.icon}</span>
                            <span className="capitalize">{agentName.replace('_', ' ')}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
                
                {/* Additional details that appear for active steps */}
                {isActive && (
                  <div className="mt-2 text-xs p-2 bg-base-100 rounded w-full">
                    {step.details}
                  </div>
                )}

                {/* Key findings for step 3 */}
                {index === 2 && isActive && (
                  <div className="mt-2 p-2 bg-red-500/10 border border-red-500/20 rounded-md text-xs w-full">
                    <span className="font-semibold block mb-1">Key Finding:</span> 
                    Cryptocurrency mining software was installed on an unauthorized p3.8xlarge instance 
                    launched with compromised IAM credentials.
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Outcomes section */}
        {iterations >= steps.length && (
          <div className="mt-6 p-4 bg-accent/10 border border-accent rounded-lg">
            <h3 className="text-lg font-bold mb-2">Investigation Outcomes</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="stat bg-base-100 rounded-lg">
                <div className="stat-figure text-secondary">💰</div>
                <div className="stat-title">Cost Impact</div>
                <div className="stat-value text-secondary">$2,100</div>
                <div className="stat-desc">Additional expenses</div>
              </div>
              <div className="stat bg-base-100 rounded-lg">
                <div className="stat-figure text-error">⏱️</div>
                <div className="stat-title">Response Time</div>
                <div className="stat-value text-error">1-2 days</div>
                <div className="stat-desc">To normal spending</div>
              </div>
              <div className="stat bg-base-100 rounded-lg">
                <div className="stat-figure text-primary">💸</div>
                <div className="stat-title">Potential Recovery</div>
                <div className="stat-value text-primary">40-60%</div>
                <div className="stat-desc">Service credits</div>
              </div>
              <div className="stat bg-base-100 rounded-lg">
                <div className="stat-figure text-success">🛡️</div>
                <div className="stat-title">Risk Reduction</div>
                <div className="stat-value text-success">80%</div>
                <div className="stat-desc">After fixes</div>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  // Get agent activity status
  const getAgentStatus = (agentName) => {
    if (!isRunning) return 'idle';
    const isActive = Math.random() > 0.5;
    const lastMsg = [...messages].reverse().find(m => m.agent === agentName);
    if (lastMsg && lastMsg.content.includes('NEXT_STEP')) return 'delegating';
    if (lastMsg && lastMsg.content.includes('CONTINUE')) return 'processing';
    return isActive ? 'active' : 'standby';
  };

  // Add a helper function to extract classifier decisions for each iteration
  const getClassifierDecisions = () => {
    const decisions = {};
    
    // Find classifier messages in each iteration
    messages.forEach(msg => {
      if (msg.agent === 'classifier' && msg.iteration) {
        decisions[msg.iteration] = msg.content;
      }
    });
    
    return decisions;
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
        {/* Sidebar with Agent Status and Visualization Toggle */}
        <div className="bg-base-100 rounded-box shadow-lg p-4 hidden lg:flex lg:flex-col overflow-auto">
          <h2 className="font-bold text-lg mb-4">Agent Status</h2>
          
          <div className="space-y-4 flex-1 overflow-y-auto">
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
            
            <div className="divider">
              <div className="flex items-center gap-2">
                <span>Agents</span>
                {selectedAgent && (
                  <div 
                    className="badge badge-sm badge-outline cursor-pointer"
                    onClick={() => setSelectedAgent(null)}
                  >
                    Clear Filter
                  </div>
                )}
              </div>
            </div>
            
            {Object.entries(agents).map(([name, agent]) => (
              <div 
                key={name} 
                className={`flex items-center p-2 rounded-lg mb-2 cursor-pointer transition-all duration-200 border-2 ${
                  selectedAgent === name 
                    ? `border-${agent.color.replace('bg-', '')} ${agent.color.replace('bg-', 'bg-')}/10` 
                    : 'border-transparent bg-base-200 hover:bg-base-300'
                }`}
                onClick={() => setSelectedAgent(selectedAgent === name ? null : name)}
              >
                <div className={`avatar placeholder mr-2`}>
                  <div className={`${agent.color} text-white rounded-full w-8`}>
                    <span>{agent.icon}</span>
                  </div>
                </div>
                <div className="flex-1">
                  <div className="font-medium capitalize">{name.replace('_', ' ')}</div>
                  <div className="text-xs opacity-70">{agent.responses} responses</div>
                </div>
                <div className="badge badge-sm" data-agent-status={getAgentStatus(name)}>
                  {(() => {
                    const status = getAgentStatus(name);
                    switch(status) {
                      case 'active': return (
                        <><span className="w-2 h-2 rounded-full bg-success animate-pulse mr-1"></span>Active</>
                      );
                      case 'delegating': return (
                        <><span className="w-2 h-2 rounded-full bg-warning mr-1"></span>Delegating</>
                      );
                      case 'processing': return (
                        <><span className="w-2 h-2 rounded-full bg-info mr-1"></span>Processing</>
                      );
                      case 'standby': return (
                        <><span className="w-2 h-2 rounded-full bg-secondary mr-1"></span>Standby</>
                      );
                      default: return (
                        <><span className="w-2 h-2 rounded-full bg-neutral mr-1"></span>Idle</>
                      );
                    }
                  })()}
                </div>
              </div>
            ))}
            
            <div className="mt-auto pt-4 space-y-4">
              {iterations > 0 && (
                <button 
                  className="btn btn-secondary w-full btn-sm"
                  onClick={() => setShowSteps(!showSteps)}
                >
                  {showSteps ? 'Hide Process Steps' : 'Show Process Steps'}
                </button>
              )}
              
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
            </div>
          </div>
        </div>
        
        {/* Messages and Steps Visualization */}
        <div className="col-span-1 lg:col-span-3 flex flex-col h-full max-h-full overflow-hidden">
          {/* Mobile Controls */}
          <div className="lg:hidden mb-4 space-y-2">
            <div className="flex gap-2">
              <button 
                className={`btn btn-primary flex-1 ${isRunning ? 'btn-disabled' : ''}`}
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
              
              {iterations > 0 && (
                <button 
                  className="btn btn-secondary"
                  onClick={() => setShowSteps(!showSteps)}
                >
                  {showSteps ? 'Hide Steps' : 'Show Steps'}
                </button>
              )}
            </div>
            
            <div className="stats shadow w-full">
              <div className="stat">
                <div className="stat-title">Iterations</div>
                <div className="stat-value text-lg">{iterations}</div>
              </div>
              <div className="stat">
                <div className="stat-title">Status</div>
                <div className="stat-value text-lg">{isRunning ? 'Running' : 'Ready'}</div>
              </div>
            </div>
            
            {selectedAgent && (
              <div className="alert alert-info py-2">
                <div>
                  <span>Filtering by: {selectedAgent.replace('_', ' ')}</span>
                  <button 
                    className="btn btn-xs btn-ghost ml-2"
                    onClick={() => setSelectedAgent(null)}
                  >
                    Clear
                  </button>
                </div>
              </div>
            )}
            
            {/* Mobile agent selector */}
            <div className="flex flex-wrap gap-1">
              {Object.entries(agents).map(([name, agent]) => (
                <div 
                  key={name}
                  className={`badge ${selectedAgent === name ? agent.color.replace('bg-', 'badge-') : 'badge-outline'} gap-1 cursor-pointer`}
                  onClick={() => setSelectedAgent(selectedAgent === name ? null : name)}
                >
                  <span>{agent.icon}</span>
                  <span className="capitalize">{name.replace('_', ' ')}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Steps Visualization (when toggled) */}
          {showSteps && (
            <div className="bg-base-100 rounded-box shadow-lg p-4 mb-4 overflow-y-auto max-h-[50vh]">
              <h2 className="font-bold text-lg mb-2 flex items-center justify-between">
                <span>Investigation Process</span>
                <button className="btn btn-circle btn-ghost btn-xs" onClick={() => setShowSteps(false)}>✕</button>
              </h2>
              {renderStepsVisualization()}
            </div>
          )}
          
          {/* Message Thread */}
          <div className="bg-base-100 rounded-box shadow-lg p-4 overflow-y-auto flex-1 relative">
            {/* Messages */}
            {filteredMessages.length === 0 ? (
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
                {filteredMessages.map((message, index) => {
                  // Special iteration separator
                  if (message.type === 'iteration') {
                    const agentsInIteration = iterationAgents[message.iteration] || [];
                    const nextIterationAgents = iterationAgents[message.iteration + 1] || [];
                    
                    // Find agents that weren't in this iteration but are in the next
                    const newAgentsInNextIteration = nextIterationAgents.filter(
                      agent => !agentsInIteration.includes(agent)
                    );
                    
                    // Find agents that are in this iteration but not in the next
                    const removedInNextIteration = agentsInIteration.filter(
                      agent => !nextIterationAgents.includes(agent) && agent !== 'classifier'
                    );
                    
                    return (
                      <div key={`iter-${index}`} className="relative">
                        {/* Iteration marker */}
                        <div className="flex justify-center my-6">
                          <div className="badge badge-lg badge-accent gap-2">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                            </svg>
                            Iteration {message.iteration} Complete
                          </div>
                        </div>
                        
                        {/* Agents involved in this iteration */}
                        {agentsInIteration.length > 0 && (
                          <div className="flex flex-col items-center mt-2 mb-6">
                            <span className="text-xs opacity-70 mb-1">Agents active in iteration {message.iteration}:</span>
                            <div className="flex flex-wrap justify-center gap-1 max-w-md">
                              {agentsInIteration.map(agentName => {
                                const agent = getAgentData(agentName);
                                return (
                                  <div 
                                    key={agentName} 
                                    className={`badge ${agent.color.replace('bg-', 'badge-')} cursor-pointer`}
                                    onClick={() => setSelectedAgent(selectedAgent === agentName ? null : agentName)}
                                  >
                                    <span>{agent.icon}</span> <span className="capitalize">{agentName.replace('_', ' ')}</span>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {/* Classifier's next iteration decision */}
                        {nextIterationAgents.length > 0 && message.iteration < iterations && (
                          <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4 my-4 max-w-md mx-auto">
                            <div className="flex items-center gap-2 mb-2">
                              <div className="bg-amber-500 text-white rounded-full w-8 h-8 flex items-center justify-center">
                                <span>🧠</span>
                              </div>
                              <span className="font-bold">Classifier's Decision for Iteration {message.iteration + 1}</span>
                            </div>
                            
                            <p className="text-sm mb-3">
                              {message.iteration === 1 
                                ? "Based on initial findings, the classifier selected these agents for the remediation planning phase:" 
                                : "The classifier coordinated these agents for the final recommendations:"}
                            </p>
                            
                            <div className="grid grid-cols-2 gap-2">
                              {nextIterationAgents
                                .filter(name => name !== 'classifier')
                                .map(agentName => {
                                  const agent = getAgentData(agentName);
                                  const isNewlySelected = newAgentsInNextIteration.includes(agentName);
                                  
                                  return (
                                    <div 
                                      key={agentName}
                                      className={`flex items-center gap-2 p-2 rounded-md cursor-pointer ${
                                        isNewlySelected ? 'bg-success/10 border border-success/20' : 'bg-base-100'
                                      }`}
                                      onClick={() => setSelectedAgent(selectedAgent === agentName ? null : agentName)}
                                    >
                                      <div className={`${agent.color} text-white rounded-full w-6 h-6 flex items-center justify-center`}>
                                        <span>{agent.icon}</span>
                                      </div>
                                      <div>
                                        <span className="text-xs capitalize">{agentName.replace('_', ' ')}</span>
                                        {isNewlySelected && (
                                          <span className="block text-xs text-success">Newly added</span>
                                        )}
                                      </div>
                                    </div>
                                  );
                                })
                              }
                            </div>
                            
                            {/* Show agents that were removed */}
                            {removedInNextIteration.length > 0 && (
                              <div className="mt-3 pt-2 border-t border-base-300">
                                <p className="text-xs mb-2">Agents no longer needed for the next iteration:</p>
                                <div className="flex flex-wrap gap-1">
                                  {removedInNextIteration.map(agentName => {
                                    const agent = getAgentData(agentName);
                                    return (
                                      <div 
                                        key={agentName}
                                        className="badge badge-outline badge-sm opacity-50"
                                      >
                                        <span>{agent.icon}</span> <span className="capitalize">{agentName.replace('_', ' ')}</span>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            )}
                            
                            <div className="mt-3 text-xs text-center opacity-70">
                              {message.iteration === 1 
                                ? "Shifting focus to detailed remediation planning" 
                                : "Focusing on comprehensive final recommendations"}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  }
                  
                  // Normal message
                  const isUser = message.role === 'user';
                  const isSystem = message.role === 'system';
                  const agentData = !isUser && !isSystem && message.agent ? getAgentData(message.agent) : null;
                  const isClassifierDecision = message.agent === 'classifier' && (
                    message.content.includes('help investigate') || 
                    message.content.includes('coordinate with specialized agents') ||
                    message.content.includes('NEXT_STEP') ||
                    message.content.includes('select specialized agents') ||
                    message.id?.includes('classifier-decision')
                  );
                  
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
                            <div 
                              className={`${agentData?.color || 'bg-secondary'} text-white rounded-full w-full h-full flex items-center justify-center cursor-pointer`}
                              onClick={() => setSelectedAgent(selectedAgent === message.agent ? null : message.agent)}
                            >
                              <span>{agentData?.icon || '🤖'}</span>
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="chat-header">
                        {isUser ? 'You' : isSystem ? 'System' : (
                          <span 
                            className="capitalize cursor-pointer hover:underline"
                            onClick={() => setSelectedAgent(selectedAgent === message.agent ? null : message.agent)}
                          >
                            {message.agent?.replace('_', ' ') || 'Assistant'}
                          </span>
                        )}
                        <time className="text-xs opacity-50 ml-1">{new Date(message.timestamp || Date.now()).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</time>
                      </div>
                      <div className={`chat-bubble ${
                        isUser 
                          ? 'chat-bubble-primary' 
                          : isSystem 
                            ? 'chat-bubble-accent' 
                            : message.agent === 'ec2_agent'
                              ? 'chat-bubble-blue-500'
                              : message.agent === 'billing_agent'
                                ? 'chat-bubble-green-500'
                                : message.agent === 'security_agent'
                                  ? 'chat-bubble-red-500'
                                  : message.agent === 'logs_agent'
                                    ? 'chat-bubble-purple-500'
                                    : message.agent === 'classifier'
                                      ? 'chat-bubble-amber-500'
                                      : 'chat-bubble-secondary'
                        } shadow-md max-w-4xl`}>
                        <ReactMarkdown components={components}>
                          {message.content}
                        </ReactMarkdown>
                        
                        {/* Command keywords highlight */}
                        {(message.content.includes('NEXT_STEP') || message.content.includes('CONTINUE')) && (
                          <div className="mt-2 text-xs bg-base-300 rounded-md p-1 font-mono">
                            {message.content.includes('NEXT_STEP') ? (
                              <span className="text-warning">NEXT_STEP: Classifier is delegating to another agent</span>
                            ) : (
                              <span className="text-info">CONTINUE: Requesting additional processing by agents</span>
                            )}
                          </div>
                        )}

                        {/* If this is the classifier making a decision, show the delegation visually */}
                        {isClassifierDecision && (
                          <div className="mt-3 pt-2 border-t border-amber-500/30">
                            <div className="text-sm font-medium mb-2 flex items-center gap-1">
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" className="w-5 h-5 text-amber-500">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                              </svg>
                              <span>Classifier is making an orchestration decision</span>
                            </div>
                            
                            <div className="bg-amber-500/5 p-3 rounded-lg border border-amber-500/20">
                              <div className="text-xs font-medium mb-2">Evaluating and selecting agents for {message.iteration ? `iteration ${message.iteration}` : 'initial analysis'}:</div>
                              <div className="grid grid-cols-2 gap-2">
                                {Object.entries(agents)
                                  .filter(([name]) => name !== 'classifier')
                                  .map(([name, agent]) => {
                                    const isSelected = message.iteration && iterationAgents[message.iteration]?.includes(name);
                                    // For the first classifier message, assume all agents are selected
                                    const isInitialSelect = !message.iteration && message.content.includes('coordinate with specialized agents');
                                    const isActive = isSelected || isInitialSelect;
                                    
                                    return (
                                      <div 
                                        key={name}
                                        className={`flex items-center gap-1 p-2 rounded border transition-all ${
                                          isActive 
                                            ? `${agent.color.replace('bg-', 'bg-')}/10 border-${agent.color.replace('bg-', '')}/30` 
                                            : 'bg-base-200/30 border-base-300'
                                        }`}
                                      >
                                        <div className={`${isActive ? agent.color : 'bg-base-300'} text-white rounded-full w-6 h-6 flex items-center justify-center`}>
                                          <span>{agent.icon}</span>
                                        </div>
                                        <div className="flex-1">
                                          <span className="text-xs capitalize">{name.replace('_', ' ')}</span>
                                          {isActive && (
                                            <span className="badge badge-xs badge-success ml-1">Selected</span>
                                          )}
                                        </div>
                                      </div>
                                    );
                                  })
                                }
                              </div>
                              
                              <div className="mt-3 pt-2 border-t border-amber-500/20">
                                <div className="flex justify-between items-center text-xs">
                                  <span className="font-medium">Current Phase:</span>
                                  <span className="badge badge-sm badge-warning">
                                    {message.iteration === 1 
                                      ? "Initial findings analysis" 
                                      : message.iteration === 2 
                                        ? "Remediation planning"
                                        : message.iteration === 3
                                          ? "Implementation timeline"
                                          : "Issue assessment"}
                                  </span>
                                </div>
                                
                                <div className="flex justify-between items-center mt-2 text-xs">
                                  <span className="font-medium">Next Action:</span>
                                  <span className="badge badge-sm badge-info">
                                    {message.content.includes('NEXT_STEP')
                                      ? "Delegating to agents"
                                      : message.content.includes('CONTINUE')
                                        ? "Continuing analysis" 
                                        : "Coordinating agents"}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </div>
                        )}
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
    </div>
  );
};

export default AgentDemo; 