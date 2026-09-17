import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import Banana from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <Banana/>
  </BrowserRouter>
);
