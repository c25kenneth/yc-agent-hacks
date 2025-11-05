import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import darkWordmark from "../assets/Dark Mode Wordmark.png";
import exampleVideo from "../assets/example.mp4";

export default function Landing() {
  const faqs = [
    {
      question: "What is Northstar?",
      answer:
        "Northstar is an AI teammate that continuously analyzes your codebase and product performance, then recommends code changes that improve your key metrics — like conversion rate, retention, or revenue.",
    },
    {
      question: "How does it connect to my codebase?",
      answer:
        "You connect your GitHub repository securely. Northstar reads your code (without making changes) to understand product flows, and can optionally open pull requests for you to review and merge.",
    },
    {
      question: "Which metrics can Northstar optimize?",
      answer:
        "You choose your north star metric — such as sign-ups, engagement, or churn rate. Northstar focuses its analysis and recommendations on improving that metric over time.",
    },
    {
      question: "Is my code data private?",
      answer:
        "Yes. Your code never leaves your private workspace. Northstar runs in a secure environment and only stores metadata needed for recommendations.",
    },
    {
      question: "When will early access launch?",
      answer:
        "We’re onboarding early access teams on a rolling basis this quarter. Join the waitlist to reserve your spot.",
    },
  ];

  const [openIndex, setOpenIndex] = useState(null);

  return (
    <div className="relative flex min-h-screen w-full flex-col items-center justify-start overflow-hidden bg-[#0f172a] text-white">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-b from-[#0f172a] via-[#111827] to-[#0f172a]" />

      <main className="relative z-10 flex flex-col items-center gap-24 px-6 py-24 max-w-6xl w-full">
        {/* Logo */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="h-auto w-full max-w-md"
        >
          <img src={darkWordmark} alt="Logo" className="h-auto w-full" />
        </motion.div>

        {/* Hero */}
        <motion.section
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1 }}
          className="flex flex-col items-center text-center gap-6"
        >
          <h1 className="text-5xl md:text-6xl font-light leading-tight bg-gradient-to-r from-white via-gray-300 to-gray-500 bg-clip-text text-transparent">
            What if your product could <span className="font-medium">improve itself?</span>
          </h1>
          <p className="max-w-2xl text-lg text-gray-400 font-light">
            Northstar monitors your metrics and recommends AI-driven code changes
            that directly improve performance — conversion rate, retention, or revenue.
          </p>

          {/* Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 mt-6">
            <a
              href="https://tally.so/r/worWMX"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-xl bg-white px-10 py-4 text-lg font-medium text-black hover:bg-gray-100 transition shadow-lg hover:shadow-xl"
            >
              Join Early Access →
            </a>
            <a
              href="https://cal.com/your-cal-link" // replace with your real Cal.com or Calendly link
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-xl border border-white/40 px-10 py-4 text-lg font-medium text-white hover:bg-white/10 transition"
            >
              Schedule a Demo
            </a>
          </div>
        </motion.section>

        {/* Demo Video */}
        <motion.section
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
          className="w-full max-w-4xl"
        >
          <div
            className="aspect-video w-full overflow-hidden border border-gray-800 bg-gray-900"
            style={{
              borderRadius: "24px",
              boxShadow: "0 8px 30px rgba(0,0,0,0.3)",
            }}
          >
            <video className="h-full w-full object-cover" controls src={exampleVideo}>
              Your browser does not support the video tag.
            </video>
          </div>
        </motion.section>

        {/* Description */}
        <motion.section
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          transition={{ duration: 1 }}
          className="max-w-3xl text-center text-gray-300 text-lg leading-relaxed font-light"
        >
          Northstar helps teams continuously improve their key metrics — conversion
          rate, retention, and revenue — by analyzing your codebase and generating
          targeted improvement suggestions. Think of it as your AI growth engineer, always on.
        </motion.section>

        {/* How It Works */}
        <motion.section
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9 }}
          className="grid grid-cols-1 md:grid-cols-3 gap-10 text-center w-full max-w-5xl"
        >
          {[
            {
              title: "1. Connect Your Repo",
              desc: "Northstar syncs with your codebase and tracks the metric you care about most.",
            },
            {
              title: "2. Analyze Performance",
              desc: "It maps which parts of your product drive your key results — and which hold you back.",
            },
            {
              title: "3. Suggest Code Changes",
              desc: "Northstar generates pull requests with data-backed improvements you can merge directly.",
            },
          ].map((item, i) => (
            <div
              key={i}
              className="flex flex-col items-center gap-3 px-4 py-6 rounded-2xl bg-white/5 backdrop-blur-sm border border-gray-800"
            >
              <div className="text-2xl font-medium text-white">{item.title}</div>
              <div className="text-gray-400 text-base leading-relaxed">{item.desc}</div>
            </div>
          ))}
        </motion.section>

        {/* Features */}
        <motion.section
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9 }}
          className="flex flex-col items-center gap-10 mt-10"
        >
          <h2 className="text-3xl font-semibold text-white">Why Teams Love Northstar</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 text-center max-w-5xl">
            {[
              {
                title: "Metric-Aware AI",
                desc: "Every recommendation is grounded in improving your chosen north star metric.",
              },
              {
                title: "Code-Level Insights",
                desc: "Understand how each code change impacts user behavior and business outcomes.",
              },
              {
                title: "Automatic PRs",
                desc: "Northstar opens ready-to-merge pull requests with concrete improvements.",
              },
            ].map((item, i) => (
              <div
                key={i}
                className="flex flex-col items-center gap-2 p-6 rounded-2xl bg-white/5 border border-gray-800 hover:bg-white/10 transition"
              >
                <div className="text-lg font-semibold text-white">{item.title}</div>
                <p className="text-gray-400 text-sm">{item.desc}</p>
              </div>
            ))}
          </div>
        </motion.section>

        {/* FAQ */}
        <motion.section
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 1 }}
          className="w-full max-w-3xl mt-20"
        >
          <h2 className="text-3xl font-semibold text-center mb-8">FAQs</h2>
          <div className="divide-y divide-gray-800 border border-gray-800 rounded-2xl overflow-hidden">
            {faqs.map((faq, index) => (
              <div key={index} className="py-5 px-6">
                <button
                  onClick={() => setOpenIndex(openIndex === index ? null : index)}
                  className="w-full flex justify-between items-center text-left"
                >
                  <span className="text-lg text-gray-200 font-medium">{faq.question}</span>
                  <span className="text-gray-400 text-2xl">
                    {openIndex === index ? "−" : "+"}
                  </span>
                </button>
                <AnimatePresence>
                  {openIndex === index && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3 }}
                      className="overflow-hidden"
                    >
                      <p className="mt-3 text-gray-400 text-sm leading-relaxed">{faq.answer}</p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            ))}
          </div>
        </motion.section>

        {/* Final CTA */}
        <motion.section
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          transition={{ duration: 1.2 }}
          className="flex flex-col items-center text-center mt-16"
        >
          <h3 className="text-2xl md:text-3xl font-light text-gray-100 mb-4">
            Your product’s next growth engineer is AI.
          </h3>
          <div className="flex flex-col sm:flex-row gap-4 mt-4">
            <a
              href="https://tally.so/r/worWMX"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-xl bg-white px-10 py-4 text-lg font-medium text-black hover:bg-gray-100 transition shadow-lg hover:shadow-xl"
            >
              Join Early Access →
            </a>
            <a
              href="https://cal.com/your-cal-link"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-xl border border-white/40 px-10 py-4 text-lg font-medium text-white hover:bg-white/10 transition"
            >
              Schedule a Demo
            </a>
          </div>
        </motion.section>
      </main>
    </div>
  );
}
