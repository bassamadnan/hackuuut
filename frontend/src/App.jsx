import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import About from "./pages/About";
import Home from "./pages/Home";
import Chat from "./pages/Chat";
import ToolGenerator from "./components/ToolGenerator";

function App() {
  return (
    <Router>
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/tools" element={<ToolGenerator />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/about" element={<About />} />
      </Routes>
    </Router>
  );
}

export default App; 