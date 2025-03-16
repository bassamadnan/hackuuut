// ToolGenerator.jsx
import { useState, useEffect, useRef } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

const ToolGenerator = () => {
  const [query, setQuery] = useState('');
  const [agentName, setAgentName] = useState('AWS Cloud Manager');
  const [agentDescription, setAgentDescription] = useState('Agent for managing AWS cloud resources and infrastructure');
  const [generatedCode, setGeneratedCode] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [functionName, setFunctionName] = useState('');
  const [feedback, setFeedback] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isFeedbackLoading, setIsFeedbackLoading] = useState(false);
  const [error, setError] = useState('');
  const [approved, setApproved] = useState(false);
  const [feedbackMode, setFeedbackMode] = useState(false);
  
  // Refs for scrolling
  const codeRef = useRef(null);
  const queryInputRef = useRef(null);
  const feedbackInputRef = useRef(null);

  // Default tools for the agent
  const [tools, setTools] = useState([
    {
      "name": "list_ec2_instances_tool",
      "description": "Lists all EC2 instances in a specified region"
    },
    {
      "name": "start_ec2_instance_tool",
      "description": "Starts an EC2 instance with the given instance ID"
    }
  ]);

  // Scroll to generated code when it's available
  useEffect(() => {
    if (generatedCode && codeRef.current) {
      setTimeout(() => {
        codeRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 100);
    }
  }, [generatedCode]);

  // Focus on feedback input when feedback mode is enabled
  useEffect(() => {
    if (feedbackMode && feedbackInputRef.current) {
      feedbackInputRef.current.focus();
    }
  }, [feedbackMode]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    setApproved(false);
    setFeedbackMode(false);
    
    try {
      const response = await fetch('http://localhost:8000/generate-tool', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          query,
          agent_name: agentName,
          agent_description: agentDescription,
          tools: tools,
          session_id: sessionId
        }),
      });

      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error);
      }
      
      setGeneratedCode(data.code);
      setSessionId(data.session_id);
      setFunctionName(data.function_name);
    } catch (error) {
      setError('Error generating tool: ' + error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFeedbackSubmit = async (e) => {
    e.preventDefault();
    setIsFeedbackLoading(true);
    setError('');
    
    try {
      const response = await fetch('http://localhost:8000/feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          feedback,
          session_id: sessionId,
          agent_name: agentName,
          agent_description: agentDescription,
          tools: tools,
          query: query
        }),
      });

      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error);
      }
      
      setGeneratedCode(data.code);
      setFunctionName(data.function_name);
      setFeedback('');
      setFeedbackMode(false);
    } catch (error) {
      setError('Error processing feedback: ' + error.message);
    } finally {
      setIsFeedbackLoading(false);
    }
  };

  const handleApprove = async () => {
    try {
      const response = await fetch('http://localhost:8000/approve-tool', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          agent_name: agentName,
          code: generatedCode,
          function_name: functionName,
          session_id: sessionId
        })
      });
      
      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error);
      }
      
      setApproved(true);
      setFeedbackMode(false);
    } catch (error) {
      setError('Error approving tool: ' + error.message);
    }
  };

  const toggleFeedbackMode = () => {
    setFeedbackMode(!feedbackMode);
  };

  // Handle keypress in query textarea
  const handleQueryKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (query.trim() && agentName && !isLoading && !feedbackMode) {
        handleSubmit(e);
      }
    }
  };

  // Handle keypress in feedback textarea
  const handleFeedbackKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (feedback.trim() && !isFeedbackLoading) {
        handleFeedbackSubmit(e);
      }
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-base-300 to-base-100 py-8">
      <div className="container mx-auto p-4 max-w-4xl">
        <div className="card bg-base-200 shadow-2xl">
          <div className="card-body">
            <h1 className="card-title text-3xl mb-6 text-primary font-bold">Tool Generator</h1>
            
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="form-control">
                  <label className="label">
                    <span className="label-text font-medium">Agent Name</span>
                  </label>
                  <input 
                    type="text"
                    className="input input-bordered input-primary w-full"
                    value={agentName}
                    onChange={(e) => setAgentName(e.target.value)}
                    required
                    disabled={isLoading || feedbackMode}
                  />
                </div>
                
                <div className="form-control">
                  <label className="label">
                    <span className="label-text font-medium">Agent Description</span>
                  </label>
                  <textarea 
                    className="textarea textarea-bordered textarea-primary h-12" 
                    value={agentDescription}
                    onChange={(e) => setAgentDescription(e.target.value)}
                    required
                    disabled={isLoading || feedbackMode}
                  ></textarea>
                </div>
              </div>
              
              <div className="form-control">
                <label className="label">
                  <span className="label-text font-medium">What should the tool do?</span>
                  <span className="label-text-alt text-info">Press Enter to submit</span>
                </label>
                <textarea 
                  ref={queryInputRef}
                  className="textarea textarea-bordered textarea-primary h-24" 
                  placeholder="e.g., delete an EC2 instance with given instance ID"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleQueryKeyDown}
                  required
                  disabled={isLoading || feedbackMode}
                ></textarea>
              </div>
              
              <div className="card-actions justify-end">
                <button 
                  type="submit" 
                  className="btn btn-primary"
                  disabled={isLoading || !query.trim() || !agentName || feedbackMode}
                >
                  {isLoading ? (
                    <>
                      <span className="loading loading-spinner loading-sm"></span>
                      Generating...
                    </>
                  ) : (
                    <>
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      Generate Tool
                    </>
                  )}
                </button>
              </div>
            </form>
            
            {error && (
              <div className="alert alert-error mt-6 shadow-lg">
                <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>{error}</span>
                <button className="btn btn-sm btn-circle btn-ghost" onClick={() => setError('')}>×</button>
              </div>
            )}
            
            {generatedCode && (
              <div className="mt-8 border-t border-base-300 pt-6" ref={codeRef}>
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-4">
                  <h2 className="text-2xl font-bold text-secondary">
                    <span className="mr-2">⚙️</span>
                    {functionName}
                  </h2>
                  <div className="flex flex-wrap gap-2">
                    {!approved ? (
                      <>
                        <button 
                          className="btn btn-sm btn-success"
                          onClick={handleApprove}
                          disabled={feedbackMode}
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                          Approve
                        </button>
                        <button 
                          className="btn btn-sm btn-info"
                          onClick={toggleFeedbackMode}
                          disabled={approved}
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                          {feedbackMode ? 'Cancel Feedback' : 'Provide Feedback'}
                        </button>
                        <button 
                          className="btn btn-sm btn-error"
                          onClick={() => {
                            setGeneratedCode('');
                            setFeedbackMode(false);
                          }}
                          disabled={feedbackMode}
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                          Reject
                        </button>
                      </>
                    ) : (
                      <div className="badge badge-success gap-2 p-3">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        Approved
                      </div>
                    )}
                  </div>
                </div>
                
                <div className="rounded-box shadow-lg overflow-hidden">
                  <SyntaxHighlighter
                    language="python"
                    style={vscDarkPlus}
                    customStyle={{
                      margin: 0,
                      padding: '1.5rem',
                      borderRadius: '0.5rem',
                      fontSize: '0.95rem',
                      lineHeight: '1.5',
                    }}
                    showLineNumbers={true}
                  >
                    {generatedCode}
                  </SyntaxHighlighter>
                </div>
                
                {!approved && (
                  <div className="flex justify-end mt-2">
                    <button 
                      className="btn btn-sm btn-ghost text-info"
                      onClick={() => {
                        navigator.clipboard.writeText(generatedCode);
                        // Show a toast or some feedback that code was copied
                      }}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                      </svg>
                      Copy Code
                    </button>
                  </div>
                )}
                
                {feedbackMode && (
                  <div className="mt-6 p-4 bg-base-300 rounded-box shadow-md">
                    <form onSubmit={handleFeedbackSubmit}>
                      <div className="form-control mb-3">
                        <label className="label">
                          <span className="label-text font-medium">Feedback</span>
                          <span className="label-text-alt text-info">Press Enter to submit</span>
                        </label>
                        <textarea 
                          ref={feedbackInputRef}
                          className="textarea textarea-bordered textarea-info h-28" 
                          placeholder="What would you like to improve about this tool?"
                          value={feedback}
                          onChange={(e) => setFeedback(e.target.value)}
                          onKeyDown={handleFeedbackKeyDown}
                          required
                        ></textarea>
                      </div>
                      
                      <div className="card-actions justify-end">
                        <button 
                          type="submit" 
                          className="btn btn-info"
                          disabled={isFeedbackLoading || !feedback.trim()}
                        >
                          {isFeedbackLoading ? (
                            <>
                              <span className="loading loading-spinner loading-sm"></span>
                              Processing...
                            </>
                          ) : (
                            <>
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                              </svg>
                              Submit Feedback
                            </>
                          )}
                        </button>
                      </div>
                    </form>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ToolGenerator;