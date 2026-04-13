import { Router, type IRouter } from "express";
import healthRouter from "./health";
import columnsRouter from "./columns";
import cardsRouter from "./cards";
import projectsRouter from "./projects";

const router: IRouter = Router();

router.use(healthRouter);
router.use(columnsRouter);
router.use(cardsRouter);
router.use(projectsRouter);

export default router;
