import ChatContainer from './components/chat/ChatContainer';

export default function Home() {
  return (
    <div className="grid grid-rows-[20px_1fr_20px] items-center justify-items-center min-h-screen p-8 pb-20 gap-16 sm:p-20 font-[family-name:var(--font-geist-sans)]">
      <main className="flex flex-col gap-8 row-start-2 items-center sm:items-start">
        <h1 className="text-2xl font-bold">Welcome to Agentic Chatbot</h1>

        {/* Chat Interface */}
        <div className="w-full max-w-4xl">
          <ChatContainer />
        </div>
      </main>
    </div>
  );
}