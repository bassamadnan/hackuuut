import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Leaderboard from "./pages/Leaderboard";
import Tasks from "./pages/Tasks";
import Papers from "./pages/Papers";
import About from "./pages/About";
import ToolGenerator from "./components/ToolGenerator";

function App() {
  return (
    <Router>
      <Navbar />
      <Routes>
        <Route path="/" element={<ToolGenerator />} />
        <Route path="/leaderboard" element={<Leaderboard />} />
        <Route path="/tasks" element={<Tasks />} />
        <Route path="/papers" element={<Papers />} />
        <Route path="/about" element={<About />} />
      </Routes>
    </Router>
  );
}

export default App;