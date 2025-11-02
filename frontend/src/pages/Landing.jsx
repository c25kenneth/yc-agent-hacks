import darkWordmark from "../assets/Dark Mode Wordmark.png";
import exampleVideo from "../assets/example.mp4";

export default function Landing() {
  return (
    <div className="relative flex min-h-screen w-full items-center justify-center overflow-hidden bg-[#111827]">
      <div className="flex flex-col items-center gap-10 px-6 max-w-5xl w-full">
        {/* Wordmark */}
        <div className="h-auto w-full max-w-md">
          <img
            src={darkWordmark}
            alt="Logo"
            className="h-auto w-full"
          />
        </div>

        {/* Tagline */}
        <div
          className="text-center text-3xl font-light leading-snug text-gray-200"
          style={{ fontFamily: "Inter, sans-serif" }}
        >
          <div>What if your product could improve itself?</div>
        </div>

        {/* Demo Video Card */}
        <div className="w-full">
          <div
            className="aspect-video w-full overflow-hidden border border-gray-800 bg-gray-900"
            style={{
              borderRadius: '24px',
              boxShadow: '0 8px 24px rgba(0,0,0,0.2)'
            }}
          >
            <video
              className="h-full w-full object-cover"
              controls
              src={exampleVideo}
            >
              Your browser does not support the video tag.
            </video>
          </div>
        </div>

        {/* Join Waitlist Button */}
        <a
          href="https://tally.so/r/worWMX"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded bg-white px-12 py-4 text-lg font-medium text-black hover:bg-gray-100 transition inline-block text-center"
          style={{
            textDecoration: 'none'
          }}
        >
          Join Early Access →
        </a>
      </div>

      {/* Powered by Footer */}
      <div className="absolute bottom-6 w-full text-center text-sm text-gray-400" style={{ opacity: 0.5 }}>
        Powered by{" "}
        <a
          href="https://metorial.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:underline"
        >
          Metorial
        </a>
        ,{" "}
        <a
          href="https://www.morphllm.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:underline"
        >
          Morph
        </a>
        , and{" "}
        <a
          href="https://runcaptain.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:underline"
        >
          Captain
        </a>
      </div>
    </div>
  );
}
