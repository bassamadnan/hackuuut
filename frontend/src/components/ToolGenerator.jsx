// ToolGenerator.jsx
import { useState, useEffect } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

const ToolGenerator = () => {
  const [query, setQuery] = useState('');
  const [agents, setAgents] = useState([]);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [generatedCode, setGeneratedCode] = useState('');
  const [sessionId, setSessionId] = useState('');
  const [feedback, setFeedback] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isFeedbackLoading, setIsFeedbackLoading] = useState(false);
  const [isAgentsLoading, setIsAgentsLoading] = useState(true);
  const [error, setError] = useState('');
  const [approved, setApproved] = useState(false);
  const [feedbackMode, setFeedbackMode] = useState(false);

  // Fetch agents on component mount
  useEffect(() => {
    fetchAgents();
  }, []);

  const fetchAgents = async () => {
    try {
      const response = await fetch('http://localhost:8000/agents');
      const data = await response.json();
      setAgents(data.agents);
      
      if (data.agents.length > 0) {
        setSelectedAgentId(data.agents[0].id);
      }
    } catch (error) {
      setError('Error fetching agents: ' + error.message);
    } finally {
      setIsAgentsLoading(false);
    }
  };

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
          agent_id: selectedAgentId,
          session_id: sessionId
        }),
      });

      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error);
      }
      
      setGeneratedCode(data.code);
      setSessionId(data.session_id);
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
          agent_id: selectedAgentId
        }),
      });

      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error);
      }
      
      setGeneratedCode(data.code);
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
      await fetch('http://localhost:8000/approve-tool', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          agent_id: selectedAgentId,
          code: generatedCode,
          session_id: sessionId
        })
      });
      
      setApproved(true);
      setFeedbackMode(false);
    } catch (error) {
      setError('Error approving tool: ' + error.message);
    }
  };

  const toggleFeedbackMode = () => {
    setFeedbackMode(!feedbackMode);
  };

  // Get selected agent details
  const selectedAgent = agents.find(agent => agent.id === selectedAgentId);

  return (
    <div className="container mx-auto p-4 max-w-4xl">
      <div className="card bg-base-100 shadow-xl">
        <div className="card-body">
          <h1 className="card-title text-2xl mb-4">Tool Generator</h1>
          
          {isAgentsLoading ? (
            <div className="flex justify-center py-8">
              <span className="loading loading-spinner loading-lg"></span>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              <div className="form-control mb-4">
                <label className="label">
                  <span className="label-text">Select Agent</span>
                </label>
                <select 
                  className="select select-bordered w-full"
                  value={selectedAgentId}
                  onChange={(e) => setSelectedAgentId(e.target.value)}
                  required
                  disabled={isLoading || feedbackMode}
                >
                  {agents.map(agent => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name}
                    </option>
                  ))}
                </select>
                
                {selectedAgent && (
                  <div className="mt-2 text-sm opacity-70">
                    {selectedAgent.description}
                  </div>
                )}
              </div>
              
              <div className="form-control mb-4">
                <label className="label">
                  <span className="label-text">What should the tool do?</span>
                </label>
                <textarea 
                  className="textarea textarea-bordered h-24" 
                  placeholder="e.g., delete an EC2 instance with given instance ID"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  required
                  disabled={isLoading || feedbackMode}
                ></textarea>
              </div>
              
              <div className="card-actions justify-end">
                <button 
                  type="submit" 
                  className="btn btn-primary"
                  disabled={isLoading || !query.trim() || !selectedAgentId || feedbackMode}
                >
                  {isLoading ? (
                    <>
                      <span className="loading loading-spinner loading-sm"></span>
                      Generating...
                    </>
                  ) : (
                    'Generate Tool'
                  )}
                </button>
              </div>
            </form>
          )}
          
          {error && (
            <div className="alert alert-error mt-4">
              <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{error}</span>
            </div>
          )}
          
          {generatedCode && (
            <div className="mt-6">
              <div className="flex justify-between items-center mb-2">
                <h2 className="text-xl font-bold">Generated Tool</h2>
                <div className="space-x-2">
                  {!approved ? (
                    <>
                      <button 
                        className="btn btn-sm btn-success"
                        onClick={handleApprove}
                        disabled={feedbackMode}
                      >
                        Approve
                      </button>
                      <button 
                        className="btn btn-sm btn-info"
                        onClick={toggleFeedbackMode}
                        disabled={approved}
                      >
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
                        Reject
                      </button>
                    </>
                  ) : (
                    <div className="badge badge-success p-3">Approved</div>
                  )}
                </div>
              </div>
              
              <div className="bg-base-300 rounded-box">
                <SyntaxHighlighter
                  language="python"
                  style={vscDarkPlus}
                  customStyle={{
                    margin: 0,
                    padding: '1rem',
                    borderRadius: '0.5rem',
                  }}
                >
                  {generatedCode}
                </SyntaxHighlighter>
              </div>
              
              {feedbackMode && (
                <div className="mt-4">
                  <form onSubmit={handleFeedbackSubmit}>
                    <div className="form-control mb-2">
                      <label className="label">
                        <span className="label-text">Feedback</span>
                      </label>
                      <textarea 
                        className="textarea textarea-bordered h-24" 
                        placeholder="Provide feedback on how to improve the tool..."
                        value={feedback}
                        onChange={(e) => setFeedback(e.target.value)}
                        required
                      ></textarea>
                    </div>
                    
                    <div className="card-actions justify-end">
                      <button 
                        type="submit" 
                        className="btn btn-primary"
                        disabled={isFeedbackLoading || !feedback.trim()}
                      >
                        {isFeedbackLoading ? (
                          <>
                            <span className="loading loading-spinner loading-sm"></span>
                            Processing...
                          </>
                        ) : (
                          'Submit Feedback'
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
  );
};

export default ToolGenerator;