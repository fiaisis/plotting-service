import Image from "next/image";

export default function Nav() {
  return (
    <nav className="nav">
      <div className="nav-title-container">
        <Image
          src="/logo.png"
          alt="Fia-Logo"
          height={260 / 10}
          width={759 / 10}
        />
        <strong className="title">Data Viewer</strong>
      </div>
      <div className="spacer" />
    </nav>
  );
}