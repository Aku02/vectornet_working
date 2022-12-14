import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torch.utils.tensorboard import SummaryWriter
import torch.optim as optim
import os
from ArgoverseDataset import ArgoverseForecastDataset
from vectornet import VectorNet
import logging
import warnings
warnings.filterwarnings('ignore')


def main():
    USE_GPU = True
    RUN_PARALLEL = True
    device_ids = [0, 1]
    if USE_GPU and torch.cuda.is_available():
        device = torch.device('cuda')
        if torch.cuda.device_count() <= 1:
            RUN_PARALLEL = False
            pass
    else:
        device = torch.device('cpu')
        RUN_PARALLEL = False

    learning_rate = 1e-3
    learning_rate_decay = 0.3
    cfg = dict(device=device, learning_rate=learning_rate, learning_rate_decay=learning_rate_decay,
               last_observe=30, epochs=25, print_every=2, save_every=2, batch_size=2,
               data_locate="./data/forecasting_dataset/train/", save_path="./model_ckpt/",
               log_file="./log.txt", tensorboard_path="runs/train_visualization")

    if not os.path.isdir(cfg['save_path']):
        os.mkdir(cfg['save_path'])
    writer = SummaryWriter(cfg['tensorboard_path'])
    logger = init_logger(cfg)

    argo_dst = ArgoverseForecastDataset(cfg)
    train_loader = DataLoader(dataset=argo_dst, batch_size=cfg['batch_size'], shuffle=True, num_workers=0, drop_last=True)

    model = VectorNet(traj_features=6, map_features=8, cfg=cfg)
    model.to(device)
    if RUN_PARALLEL:
        model = nn.DataParallel(model, device_ids=device_ids)
    # optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    optimizer = optim.Adadelta(model.parameters(), rho=0.9)
    # scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=learning_rate_decay)  # MultiStepLR TODO

    logger.info("Start Training...")
    do_train(model, cfg, train_loader, optimizer, scheduler=None, writer=writer, logger=logger)


def do_train(model, cfg, train_loader, optimizer, scheduler, writer, logger):
    device = cfg['device']
    print_every = cfg['print_every']
    for e in range(cfg['epochs']):
        for i, (traj_batch, map_batch) in enumerate(train_loader):
            model.train()
            traj_batch = traj_batch.to(device=device, dtype=torch.float)  # move to device, e.g. GPU
            loss = model(traj_batch, map_batch).sum()
            # save loss

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            if i % print_every == 0:
                logger.info('Epoch %d/25: Iteration %d, loss = %.4f' % (e+1, i, loss.item()))
                writer.add_scalar('training_loss', loss.item(), e)
        # scheduler.step()
        if (e+1) % cfg['save_every'] == 0:
            file_path = cfg['save_path'] + "model_epoch" + str(e+1) + ".pth"
            torch.save({
                'epoch': e,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                # 'scheduler_state_dict': scheduler.state_dict(),
                'loss': loss
            }, file_path)
            logger.info("Save model "+file_path)
    torch.save(model.state_dict(), cfg['save_path']+"model_final.pth")
    logger.info("Save final model "+cfg['save_path']+"model_final.pth")
    logger.info("Finish Training")


def init_logger(cfg):
    logger = logging.getLogger(__name__)
    logger.setLevel(level=logging.DEBUG)
    log_file = cfg['log_file']
    handler = logging.FileHandler(log_file, mode='w')
    handler.setLevel(logging.DEBUG)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.addHandler(console)
    return logger


if __name__ == "__main__":
    main()