import React from 'react';
import { useNavigate } from 'react-router-dom';

const Home = () => {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col h-screen bg-gradient-to-b from-base-300 to-base-200">
      {/* Main content */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-7xl mx-auto w-full">
          <div className="text-center my-8">
            <h2 className="text-4xl font-bold mb-4">Welcome to Moya</h2>
            <p className="text-xl mb-8 max-w-2xl mx-auto">
              A powerful framework for creating, managing, and orchestrating multiple AI agents
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-8">
            {/* Tool Generator Card */}
            <div className="card bg-base-100 shadow-md hover:shadow-lg transition-all duration-300 cursor-pointer" 
                 onClick={() => navigate('/tools')}>
              <figure className="px-10 pt-10">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-24 w-24 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </figure>
              <div className="card-body items-center text-center">
                <h2 className="card-title text-2xl">Tool Generator</h2>
                <p className="mb-4">Create custom tools for your AI agents with our intuitive tool generator</p>
                <div className="card-actions">
                  <button className="btn btn-primary shadow-sm">Get Started</button>
                </div>
              </div>
            </div>
            
            {/* Chat Interface Card */}
            <div className="card bg-base-100 shadow-md hover:shadow-lg transition-all duration-300 cursor-pointer"
                 onClick={() => navigate('/chat')}>
              <figure className="px-10 pt-10">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-24 w-24 text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
              </figure>
              <div className="card-body items-center text-center">
                <h2 className="card-title text-2xl">Chat Interface</h2>
                <p className="mb-4">Interact with your AI agents through our intuitive chat interface</p>
                <div className="card-actions">
                  <button className="btn btn-secondary shadow-sm">Start Chatting</button>
                </div>
              </div>
            </div>

            {/* Agent Demo Card */}
            <div className="card bg-base-100 shadow-md hover:shadow-lg transition-all duration-300 cursor-pointer"
                 onClick={() => navigate('/agent-demo')}>
              <div className="absolute -top-2 -right-2">
                <div className="badge badge-accent py-3 px-4">NEW</div>
              </div>
              <figure className="px-10 pt-10">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-24 w-24 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                </svg>
              </figure>
              <div className="card-body items-center text-center">
                <h2 className="card-title text-2xl">AWS Cost Demo</h2>
                <p className="mb-4">See how multiple AI agents collaborate to solve complex AWS cost issues</p>
                <div className="card-actions">
                  <button className="btn btn-accent shadow-sm">Try Demo</button>
                </div>
              </div>
            </div>
          </div>
          
          <div className="text-center mt-8 mb-4">
            <p className="text-sm opacity-70">
              Powered by Moya - Meta Orchestration framework for Your Agents
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Home; 