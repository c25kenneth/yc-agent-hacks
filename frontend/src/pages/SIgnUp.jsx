import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../../supabaseClient";
import darkWordmark from "../assets/Dark Mode Wordmark.png";

export default function Signup() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleSignup = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const { data, error } = await supabase.auth.signUp({
      email,
      password,
    });

    setLoading(false);

    if (error) setError(error.message);
    else if (data.user) {
      navigate("/dashboard", { replace: true });
    }
  };

  const handleGoogleSignup = async () => {
    setError("");
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: window.location.origin + '/dashboard'
      }
    });

    if (error) setError(error.message);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#111827] px-6">
      <div className="w-full max-w-md">
        {/* Wordmark */}
        <div className="mb-8 flex justify-center">
          <img src={darkWordmark} alt="Northstar" className="h-auto w-64" />
        </div>

        <form onSubmit={handleSignup} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full rounded border border-gray-700 bg-gray-900 px-4 py-2 text-white placeholder-gray-500 focus:border-gray-600 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full rounded border border-gray-700 bg-gray-900 px-4 py-2 text-white placeholder-gray-500 focus:border-gray-600 focus:outline-none"
            />
          </div>

          {error && (
            <p className="text-sm text-red-400">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded bg-white py-2 font-medium text-black hover:bg-gray-100 disabled:opacity-50"
          >
            {loading ? "Creating account..." : "Sign up"}
          </button>
        </form>

        <div className="mt-6">
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-700"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="bg-[#111827] px-2 text-gray-400">Or</span>
            </div>
          </div>

          <button
            type="button"
            onClick={handleGoogleSignup}
            className="mt-4 w-full rounded border border-gray-700 bg-gray-900 py-2 font-medium text-white hover:bg-gray-800"
          >
            Continue with Google
          </button>
        </div>

        <p className="mt-6 text-center text-sm text-gray-400">
          Already have an account?{" "}
          <a href="/login" className="text-gray-200 hover:underline">
            Log in
          </a>
        </p>
      </div>
    </div>
  );
}
