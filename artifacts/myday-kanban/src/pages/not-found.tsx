import { Link } from "wouter";
import { FileQuestion, MoveLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-background">
      <div className="max-w-md w-full px-6 text-center">
        <div className="flex justify-center mb-6">
          <div className="w-20 h-20 bg-secondary rounded-2xl flex items-center justify-center">
            <FileQuestion className="w-10 h-10 text-muted-foreground" />
          </div>
        </div>
        <h1 className="text-3xl font-display font-bold text-foreground mb-3">Page Not Found</h1>
        <p className="text-muted-foreground mb-8">
          The board or page you are looking for doesn't exist or has been removed.
        </p>
        <Link href="/" className="inline-block">
          <Button className="h-12 px-6 rounded-xl w-full sm:w-auto shadow-lg shadow-primary/20">
            <MoveLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>
        </Link>
      </div>
    </div>
  );
}
