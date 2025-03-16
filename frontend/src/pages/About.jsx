import React from 'react'

const About = () => {
  return (
    <div className="flex flex-col h-screen bg-gradient-to-b from-base-300 to-base-200">
      {/* Main content */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-5xl mx-auto w-full">
          <div className="card bg-base-100 shadow-md">
            <div className="card-body">
              <h2 className="text-3xl font-bold mb-6">Moya Framework</h2>
              
              <p className="mb-4">
                This is some GPT generated shit. Moya is a powerful multi-agent orchestration framework designed to help you create, manage, and coordinate multiple AI agents to solve complex tasks.
              </p>
              
              <h3 className="text-xl font-semibold mt-6 mb-3">Key Features</h3>
              
              <ul className="list-disc pl-6 space-y-2 mb-6">
                <li>Create specialized AI agents for different tasks</li>
                <li>Orchestrate multiple agents to work together</li>
                <li>Generate custom tools for your agents</li>
                <li>Interact with your agents through a chat interface</li>
                <li>Easily extend and customize the framework</li>
              </ul>
              
              <h3 className="text-xl font-semibold mt-6 mb-3">How It Works</h3>
              
              <p className="mb-4">
                Moya uses a director-based orchestration approach where a central director agent coordinates specialized agents to handle different aspects of a task. This allows for more efficient problem-solving and better specialization.
              </p>
              
              <div className="bg-base-200 p-4 rounded-lg shadow-inner mt-6">
                <h4 className="font-medium mb-2">Example Use Cases</h4>
                <ul className="list-disc pl-6 space-y-1">
                  <li>Cloud resource management and monitoring</li>
                  <li>Complex data analysis and reporting</li>
                  <li>Customer support and service automation</li>
                  <li>Research and information gathering</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default About