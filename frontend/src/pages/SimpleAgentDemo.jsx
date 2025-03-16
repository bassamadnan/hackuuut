import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import { useNavigate } from 'react-router-dom';
import remarkGfm from 'remark-gfm';
import '../styles/SimpleAgentDemo.css';

const SimpleAgentDemo = () => {
  const [sessionId, setSessionId] = useState(null);
  const [status, setStatus] = useState('idle');
  const [messages, setMessages] = useState([]);
  const [currentIteration, setCurrentIteration] = useState(0);
  const [error, setError] = useState(null);
  const [agentsInIteration, setAgentsInIteration] = useState({});
  const [classifierDecisions, setClassifierDecisions] = useState({});
  const navigate = useNavigate();

  // Agent colors
  const agentColors = {
    'classifier': '#4B0082', // Indigo
    'returns_agent': '#008080', // Teal
    'customer_agent': '#D2691E', // Chocolate
    'inventory_agent': '#228B22', // Forest Green
    'shipping_agent': '#B8860B', // Dark Goldenrod
  };

  // Agent display names
  const agentDisplayNames = {
    'classifier': 'Classifier',
    'returns_agent': 'Returns Policy Agent',
    'customer_agent': 'Customer History Agent',
    'inventory_agent': 'Inventory Agent',
    'shipping_agent': 'Shipping Agent',
  };

  // Start the demo
  const startDemo = async () => {
    try {
      setStatus('loading');
      setMessages([]);
      setCurrentIteration(0);
      setAgentsInIteration({});
      setClassifierDecisions({});
      
      // Initial user message describing the situation
      const userMessage = {
        id: 'user-1',
        role: 'user',
        content: "Customer Alex Johnson wants to return wireless headphones purchased 18 days ago. It's outside our standard 15-day electronics return window. Should we make an exception?",
        timestamp: new Date().toISOString(),
        iteration: 1
      };
      
      setMessages([userMessage]);
      
      const response = await axios.post('http://localhost:8001/api/simple_agent_demo/start', {
        message: userMessage.content
      });
      
      setSessionId(response.data.session_id);
      setStatus('running');
    } catch (err) {
      console.error('Error starting demo:', err);
      setError('Failed to start the demo. Please try again.');
      setStatus('error');
    }
  };

  // Poll for updates
  useEffect(() => {
    let intervalId;
    
    if (sessionId && status === 'running') {
      intervalId = setInterval(async () => {
        try {
          const response = await axios.get(`http://localhost:8001/api/simple_agent_demo/status?thread_id=${sessionId}`);
          
          if (response.data.status === 'complete') {
            setStatus('complete');
            clearInterval(intervalId);
          }
          
          // Update messages and current iteration
          setMessages(prevMsgs => {
            // Only add messages if they're not already in the state
            const existingIds = new Set(prevMsgs.map(m => m.id));
            const newMessages = [...prevMsgs];
            
            response.data.messages.forEach(msg => {
              if (!existingIds.has(msg.id)) {
                newMessages.push(msg);
              }
            });
            
            return newMessages;
          });
          
          setCurrentIteration(response.data.iterations);
          
        } catch (err) {
          console.error('Error fetching updates:', err);
          setError('Error fetching updates. Please try again.');
          setStatus('error');
          clearInterval(intervalId);
        }
      }, 1000);
    }
    
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [sessionId, status]);

  // Process messages to identify which agents are active in each iteration
  useEffect(() => {
    const iterationAgents = {};
    const decisions = {};
    
    // First, get all classifier decisions
    messages.forEach(msg => {
      if (msg.agent === 'classifier' && msg.id.includes('decision')) {
        decisions[msg.iteration] = msg.content;
      }
    });
    
    // Then, identify which agents appear in each iteration
    messages.forEach(msg => {
      if (msg.agent && msg.role === 'assistant' && !msg.id.includes('decision')) {
        if (!iterationAgents[msg.iteration]) {
          iterationAgents[msg.iteration] = new Set();
        }
        iterationAgents[msg.iteration].add(msg.agent);
      }
    });
    
    // Add classifier to every iteration since it's always active
    Object.keys(iterationAgents).forEach(iteration => {
      iterationAgents[iteration].add('classifier');
    });
    
    // Convert Sets to arrays
    const formattedAgents = Object.entries(iterationAgents).reduce((acc, [iteration, agents]) => {
      acc[iteration] = Array.from(agents);
      return acc;
    }, {});
    
    setAgentsInIteration(formattedAgents);
    setClassifierDecisions(decisions);
    
  }, [messages]);

  // Helper function to determine if a message is a classifier decision
  const isClassifierDecision = (message) => {
    return (
      message.agent === 'classifier' && 
      (message.id.includes('decision') || 
       message.content.includes('select') || 
       message.content.includes('engage'))
    );
  };

  // Helper function to extract activated and deactivated agents between iterations
  const getAgentChanges = (currentIter, nextIter) => {
    if (!agentsInIteration[currentIter] || !agentsInIteration[nextIter]) {
      return { activated: [], deactivated: [] };
    }
    
    // Filter out classifier as it's always active
    const currentAgents = new Set(agentsInIteration[currentIter].filter(a => a !== 'classifier'));
    const nextAgents = new Set(agentsInIteration[nextIter].filter(a => a !== 'classifier'));
    
    // Get activated agents (in next but not in current)
    const activated = Array.from(nextAgents).filter(agent => !currentAgents.has(agent));
    
    // Get deactivated agents (in current but not in next)
    const deactivated = Array.from(currentAgents).filter(agent => !nextAgents.has(agent));
    
    return { activated, deactivated };
  };

  return (
    <div className="simple-agent-demo container mx-auto p-4 max-w-6xl">
      <h1 className="text-2xl font-bold mb-6">Simple Multi-Agent Orchestration Demo</h1>
      <p className="mb-4 text-gray-700">
        This demo shows a customer service scenario where the classifier dynamically selects different specialized agents 
        in each iteration based on the evolving needs of the investigation.
      </p>
      
      {status === 'idle' && (
        <div className="text-center my-8">
          <button 
            className="btn btn-primary" 
            onClick={startDemo}
          >
            Start Simple Agent Demo
          </button>
          <p className="mt-4 text-sm text-gray-600">
            Scenario: A customer wants to return an electronics product outside the standard return window.
            The classifier will activate different specialized agents in each iteration to analyze and resolve the case.
          </p>
        </div>
      )}
      
      {status === 'loading' && (
        <div className="flex justify-center my-8">
          <span className="loading loading-spinner loading-lg"></span>
        </div>
      )}
      
      {error && (
        <div className="alert alert-error my-4">
          <span>{error}</span>
        </div>
      )}
      
      {(status === 'running' || status === 'complete') && (
        <div className="mt-6">
          <div className="flex justify-between mb-4">
            <h2 className="text-xl font-semibold">Agent Investigation</h2>
            <div className="badge badge-neutral text-white">
              {status === 'running' ? 'In Progress' : 'Complete'}
            </div>
          </div>
          
          {/* Iteration Progress */}
          <div className="mb-6">
            <div className="flex justify-between mb-2">
              <span className="font-medium">Progress:</span>
              <span>{currentIteration} of 3 iterations</span>
            </div>
            <progress 
              className="progress progress-primary w-full" 
              value={currentIteration} 
              max="3"
            ></progress>
          </div>
          
          {/* Agent Orchestration Model Visualization */}
          <div className="bg-base-200 p-4 rounded-lg mb-6">
            <h3 className="text-lg font-medium mb-3">How the Orchestration Works</h3>
            <div className="flex flex-wrap gap-2 items-center justify-center mb-4">
              <div className="flex flex-col items-center gap-2 p-3 bg-white rounded-lg shadow-sm">
                <div className="font-medium">All Agents Exist</div>
                <div className="flex gap-1">
                  {Object.entries(agentDisplayNames).map(([key, name]) => (
                    <span 
                      key={key} 
                      className="badge" 
                      style={{backgroundColor: agentColors[key], color: 'white'}}
                    >
                      {name}
                    </span>
                  ))}
                </div>
              </div>
              <div className="text-2xl font-light hidden md:block">→</div>
              <div className="flex flex-col items-center gap-2 p-3 bg-white rounded-lg shadow-sm">
                <div className="font-medium">Classifier Decides</div>
                <div className="flex gap-1">
                  <span 
                    className="badge" 
                    style={{backgroundColor: agentColors['classifier'], color: 'white'}}
                  >
                    {agentDisplayNames['classifier']}
                  </span>
                </div>
              </div>
              <div className="text-2xl font-light hidden md:block">→</div>
              <div className="flex flex-col items-center gap-2 p-3 bg-white rounded-lg shadow-sm">
                <div className="font-medium">Some Agents Activated</div>
                <div className="flex gap-1">
                  <span className="badge badge-success text-white">Activated Agents</span>
                </div>
              </div>
            </div>
          </div>
          
          {/* Agent Participation Table */}
          <div className="my-6 overflow-x-auto">
            <h3 className="text-lg font-medium mb-2">Agent Activation by Iteration</h3>
            <table className="table table-zebra w-full">
              <thead>
                <tr>
                  <th>Iteration</th>
                  <th>Active Agents</th>
                  <th>Changes</th>
                  <th>Classifier Decision</th>
                </tr>
              </thead>
              <tbody>
                {[1, 2, 3].map(iteration => (
                  <tr key={iteration} className={currentIteration >= iteration ? "" : "opacity-40"}>
                    <td className="font-medium">Iteration {iteration}</td>
                    <td>
                      {agentsInIteration[iteration] ? (
                        <div className="flex flex-wrap gap-1">
                          {agentsInIteration[iteration].map(agent => (
                            <span 
                              key={agent} 
                              className={`badge ${agent === 'classifier' ? 'badge-primary' : ''}`} 
                              style={{
                                backgroundColor: agent === 'classifier' ? agentColors[agent] : 'transparent', 
                                color: agent === 'classifier' ? 'white' : 'inherit',
                                border: agent !== 'classifier' ? `2px solid ${agentColors[agent]}` : 'none',
                                color: agent !== 'classifier' ? agentColors[agent] : 'white'
                              }}
                            >
                              {agentDisplayNames[agent]}
                              {agent === 'classifier' && <span className="ml-1">🧠</span>}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td>
                      {iteration > 1 && (
                        <div>
                          {(() => {
                            const { activated, deactivated } = getAgentChanges(iteration-1, iteration);
                            return (
                              <>
                                {activated.length > 0 && (
                                  <div className="flex gap-1 mb-1">
                                    <span className="text-green-600 text-sm">+ Activated:</span>
                                    {activated.map(agent => (
                                      <span 
                                        key={agent} 
                                        className="badge badge-sm badge-success"
                                      >
                                        {agentDisplayNames[agent]}
                                      </span>
                                    ))}
                                  </div>
                                )}
                                {deactivated.length > 0 && (
                                  <div className="flex gap-1">
                                    <span className="text-red-600 text-sm">- Deactivated:</span>
                                    {deactivated.map(agent => (
                                      <span 
                                        key={agent} 
                                        className="badge badge-sm badge-error"
                                      >
                                        {agentDisplayNames[agent]}
                                      </span>
                                    ))}
                                  </div>
                                )}
                                {activated.length === 0 && deactivated.length === 0 && (
                                  <span className="text-gray-400">No changes</span>
                                )}
                              </>
                            );
                          })()}
                        </div>
                      )}
                    </td>
                    <td className="max-w-sm">
                      {classifierDecisions[iteration] ? (
                        <div className="text-sm" style={{maxHeight: "80px", overflow: "auto"}}>
                          {classifierDecisions[iteration]}
                        </div>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          {/* Messages */}
          <div className="message-container my-8">
            {messages.map((message, index) => {
              // Skip type=iteration messages
              if (message.type === 'iteration') return null;
              
              const isDecision = isClassifierDecision(message);
              
              return (
                <div 
                  key={message.id}
                  className={`message ${message.role === 'user' ? 'user-message' : 'agent-message'} ${isDecision ? 'classifier-decision' : ''}`}
                >
                  {message.role === 'assistant' && (
                    <div className="agent-header" style={{ backgroundColor: agentColors[message.agent] }}>
                      <span className="agent-name">{agentDisplayNames[message.agent] || message.agent}</span>
                      <span className="iteration-badge">Iteration {message.iteration}</span>
                    </div>
                  )}
                  
                  <div className="message-content">
                    {message.role === 'user' ? (
                      <div className="user-content">{message.content}</div>
                    ) : (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {message.content}
                      </ReactMarkdown>
                    )}
                  </div>
                  
                  {/* Special visualization for classifier decisions */}
                  {isDecision && (
                    <div className="classifier-action mt-4 p-3 border border-indigo-200 bg-indigo-50 rounded-md">
                      <div className="text-sm font-semibold text-indigo-800 mb-2">
                        <span role="img" aria-label="Decision">🧠</span> Classifier activation decisions for next iteration:
                      </div>
                      
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                        {Object.entries(agentDisplayNames).filter(([key]) => key !== 'classifier').map(([agent, name]) => {
                          const nextIteration = message.iteration + 1;
                          const isSelected = agentsInIteration[nextIteration]?.includes(agent);
                          const wasSelected = agentsInIteration[message.iteration]?.includes(agent);
                          const isActivated = isSelected && !wasSelected;
                          const isDeactivated = wasSelected && !isSelected;
                          
                          return (
                            <div 
                              key={agent}
                              className={`
                                agent-selection-card p-2 rounded text-center
                                ${isSelected ? 'border-2 bg-white' : 'border bg-gray-50'}
                                ${isActivated ? 'border-green-400' : isDeactivated ? 'border-red-400' : 'border-gray-200'}
                              `}
                              style={{
                                borderColor: isSelected ? agentColors[agent] : isDeactivated ? '#f87171' : '#e5e7eb'
                              }}
                            >
                              <div className="text-sm font-medium" style={{ color: agentColors[agent] }}>
                                {name}
                              </div>
                              <div className="mt-1">
                                {isActivated && <span className="badge badge-sm badge-success">Activated</span>}
                                {isDeactivated && <span className="badge badge-sm badge-error">Deactivated</span>}
                                {isSelected && !isActivated && <span className="badge badge-sm badge-info">Active</span>}
                                {!isSelected && !isDeactivated && <span className="badge badge-sm badge-ghost">Inactive</span>}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
            
            {status === 'running' && (
              <div className="my-6 text-center">
                <span className="loading loading-dots loading-md"></span>
              </div>
            )}
          </div>
          
          {status === 'complete' && (
            <div className="my-6 text-center">
              <h3 className="text-lg font-semibold mb-4">Demo Complete</h3>
              <button 
                className="btn btn-primary"
                onClick={startDemo}
              >
                Run Demo Again
              </button>
              <button 
                className="btn btn-outline ml-4"
                onClick={() => navigate('/')}
              >
                Back to Home
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SimpleAgentDemo; 