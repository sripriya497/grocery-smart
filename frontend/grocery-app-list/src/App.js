import {BrowserRouter as Router, Routes, Route, Link, Navigate} from "react-router-dom";
import {useEffect, useState} from "react";
import {ToastContainer, toast} from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

import HomePage from "./HomePage";
import UploadPage from "./UploadPage";
import StorePage from "./StorePage";
import LoginPage from "./LoginPage";
import SignupPage from "./SignupPage";

import "./styles.css";

const App = () => {
    const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem("token"));
    const [userEmail, setUserEmail] = useState(localStorage.getItem("email") || "");

    const notifyLogout = () => toast("You have been logged out successfully!");
    const notifyLogin = () => toast("Login successful!");

    const handleLogout = () => {
        localStorage.removeItem("token");
        localStorage.removeItem("email");
        setIsLoggedIn(false);
        setUserEmail("");
        notifyLogout();
        window.location.href = "/login";
    };

    useEffect(() => {
        const handleStorageChange = () => {
            setIsLoggedIn(!!localStorage.getItem("token"));
            setUserEmail(localStorage.getItem("email") || "");
        };

        window.addEventListener("storage", handleStorageChange);
        return () => window.removeEventListener("storage", handleStorageChange);
    }, []);


    return (
        <Router>
            <header className="navbar">
                <h1>Grocery Smart 🛒</h1>
                <nav>
                    <Link to="/">Home</Link>
                    <Link to="/upload">Upload Data</Link>
                    {isLoggedIn && <span className="welcome">Welcome, {userEmail} 👋</span>}
                    {isLoggedIn ? (
                        <Link to="/" className="nav-button" onClick={handleLogout}>Logout</Link>
                    ) : (
                        <>
                            <Link to="/login">Login</Link>
                            <Link to="/signup">Signup</Link>
                        </>
                    )}
                </nav>
            </header>

            <Routes>
                <Route path="/login" element={<LoginPage/>}/>
                <Route path="/signup" element={<SignupPage/>}/>
                <Route path="/" element={<HomePage/>}/>
                <Route path="/upload" element={<UploadPage/>}/>
                <Route path="/store/:storeId" element={<StorePage/>}/>
            </Routes>
            <ToastContainer position="top-right" autoClose={3000}/>
        </Router>
    );
};

export default App;
