"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Scale, Loader2, AlertCircle } from "lucide-react";
import { authApi } from "@/lib/api";
import { saveSession } from "@/lib/auth";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setFieldErrors({});

    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setLoading(true);
    try {
      const { data } = await authApi.register({ fullName, email, password });
      saveSession(data.token, {
        userId: data.userId,
        email: data.email,
        fullName: data.fullName,
        role: data.role as "USER" | "ADMIN",
      });
      router.push("/dashboard");
    } catch (err: any) {
      const data = err?.response?.data;
      if (data?.fieldErrors) {
        setFieldErrors(data.fieldErrors);
      } else {
        setError(data?.message ?? "Registration failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const field = (name: string, label: string, type: string, value: string,
    onChange: (v: string) => void, placeholder: string, autocomplete?: string) => (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <input
        type={type}
        autoComplete={autocomplete}
        required
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 ${
          fieldErrors[name] ? "border-red-400" : "border-gray-300"
        }`}
        placeholder={placeholder}
      />
      {fieldErrors[name] && (
        <p className="text-xs text-red-600 mt-1">{fieldErrors[name]}</p>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-b from-primary-900 to-primary-800
                    flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-3 text-white mb-2">
            <Scale className="h-8 w-8 text-legal-gold" />
            <span className="text-2xl font-serif font-bold">LexRAG</span>
          </div>
          <p className="text-white/60 text-sm">Create your research account</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <h1 className="text-xl font-semibold text-gray-900 mb-6">Create account</h1>

          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200
                            rounded-lg mb-4 text-sm text-red-700">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {field("fullName", "Full name", "text", fullName, setFullName,
              "Jane Smith", "name")}
            {field("email", "Email address", "email", email, setEmail,
              "you@example.com", "email")}
            {field("password", "Password", "password", password, setPassword,
              "Minimum 8 characters", "new-password")}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Confirm password
              </label>
              <input
                type="password"
                autoComplete="new-password"
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm
                           focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !fullName || !email || !password || !confirm}
              className="btn-primary w-full justify-center py-2.5"
            >
              {loading
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Creating account…</>
                : "Create account"}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
            Already have an account?{" "}
            <Link href="/login" className="text-primary-600 hover:underline font-medium">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
