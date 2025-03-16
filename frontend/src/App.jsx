import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import About from "./pages/About";
import Home from "./pages/Home";
import Chat from "./pages/Chat";
import ToolGenerator from "./components/ToolGenerator";
import AgentDemo from "./pages/AgentDemo";
import SimpleAgentDemo from "./pages/SimpleAgentDemo";

function App() {
  return (
    <Router>
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/tools" element={<ToolGenerator />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/about" element={<About />} />
        <Route path="/agent-demo" element={<AgentDemo />} />
        <Route path="/simple-agent-demo" element={<SimpleAgentDemo />} />
      </Routes>
    </Router>
  );
}

export default App; 