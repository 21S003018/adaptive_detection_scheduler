from torch.optim.optimizer import Optimizer
from torch.optim.lr_scheduler import _LRScheduler
import torch
import torch.nn.functional as F
import math


class AdaptDectectionLR(_LRScheduler):
    def __init__(self, optimizer: torch.optim.SGD, meta_lr=2e-4, loss_decay=0.99, last_epoch: int = -1, verbose=False) -> None:
        self.last_lr_grad = [0] * len(optimizer.param_groups)
        self.accumulated_param_grad = []
        for group in optimizer.param_groups:
            tmp_accumulated_param_grad = []
            for param in group["params"]:
                tmp_accumulated_param_grad.append(torch.zeros(
                    param.size(), device=param.device))
            self.accumulated_param_grad.append(tmp_accumulated_param_grad)
        self.meta_lr = meta_lr
        self.max_lr = 0.2
        self.min_lr = 0.001
        # self.loss_decay = loss_decay
        super(AdaptDectectionLR, self).__init__(optimizer, last_epoch, verbose)
        return

    def get_lr(self) -> float:
        lrs = []
        for lr_idx, group in enumerate(self.optimizer.param_groups):
            tmp_lr = group['lr']+self.meta_lr*self.last_lr_grad[lr_idx]
            if tmp_lr > self.max_lr:
                lrs.append(self.max_lr)
            elif tmp_lr < self.min_lr:
                lrs.append(self.min_lr)
            else:
                lrs.append(tmp_lr)
        for lr_idx, group in enumerate(self.optimizer.param_groups):
            self.last_lr_grad[lr_idx] = 0
            for i, param in enumerate(group["params"]):
                self.accumulated_param_grad[lr_idx][i] = torch.zeros(param.size(), device=param.device)
        return list(lrs)

    def buffer_step(self, num_batch=1500) -> None:
        for lr_idx, group in enumerate(self.optimizer.param_groups):
            grad = 0
            for i, param in enumerate(group["params"]):
                if param.grad != None:
                    grad += torch.sum(torch.mul(self.accumulated_param_grad[lr_idx][i], param.grad.data))
                    self.accumulated_param_grad[lr_idx][i] += param.grad.data.clone()
            self.last_lr_grad[lr_idx] += grad/num_batch
        return


class AdaptDectectionMomentumLR(_LRScheduler):
    def __init__(self, optimizer: torch.optim.SGD, meta_lr=5e-5, loss_decay=0.99, last_epoch: int = -1, verbose=False) -> None:
        self.last_lr_grad = [0] * len(optimizer.param_groups)
        self.accumulated_momentum_buffer = []
        for param in optimizer.param_groups[0]["params"]:
            self.accumulated_momentum_buffer.append(torch.zeros(
                param.size(), device=param.device))
        self.meta_lr = meta_lr
        self.max_lr = 0.2
        self.min_lr = 0.001
        self.loss_decay = loss_decay
        super(AdaptDectectionMomentumLR, self).__init__(optimizer, last_epoch, verbose)
        return

    def get_lr(self) -> float:
        lrs = []
        for lr_idx, group in enumerate(self.optimizer.param_groups):
            tmp_lr = group['lr']+self.meta_lr*self.last_lr_grad[lr_idx]
            if tmp_lr > self.max_lr:
                lrs.append(self.max_lr)
            elif tmp_lr < self.min_lr:
                lrs.append(self.min_lr)
            else:
                lrs.append(tmp_lr)
        for lr_idx, group in enumerate(self.optimizer.param_groups):
            self.last_lr_grad[lr_idx] = 0
            for i, param in enumerate(group["params"]):
                self.accumulated_momentum_buffer[i] = torch.zeros(param.size(), device=param.device)
        return list(lrs)

    def buffer_step(self, num_batch=1500) -> None:
        for lr_idx, group in enumerate(self.optimizer.param_groups):
            grad = 0
            for i, param in enumerate(group["params"]):
                if param.grad != None:
                    grad += torch.sum(torch.mul(self.accumulated_momentum_buffer[i], param.grad.data))
                    self.accumulated_momentum_buffer[i] += self.optimizer.state[param]["momentum_buffer"].data.clone()
            # self.last_lr_grad[lr_idx] = self.loss_decay*self.last_lr_grad[lr_idx]+(1-self.loss_decay)/(1-self.loss_decay**num_batch)*grad
            self.last_lr_grad[lr_idx] += grad/num_batch
        return


class AdaptDectectionAdamLR(_LRScheduler):
    def __init__(self, optimizer: torch.optim.SGD, meta_lr=1e-6, loss_decay=0.99, last_epoch: int = -1, verbose=False) -> None:
        self.last_lr_grad = [0] * len(optimizer.param_groups)
        self.accumulated_adam_buffer = []
        for param in optimizer.param_groups[0]["params"]:
            self.accumulated_adam_buffer.append(torch.zeros(
                param.size(), device=param.device))
        self.meta_lr = meta_lr
        self.max_lr = 0.002
        self.min_lr = 0.00001
        self.loss_decay = loss_decay
        super(AdaptDectectionAdamLR, self).__init__(optimizer, last_epoch, verbose)
        return

    def get_lr(self) -> float:
        lrs = []
        for lr_idx, group in enumerate(self.optimizer.param_groups):
            tmp_lr = group['lr']+self.meta_lr*self.last_lr_grad[lr_idx]
            if tmp_lr > self.max_lr:
                lrs.append(self.max_lr)
            elif tmp_lr < self.min_lr:
                lrs.append(self.min_lr)
            else:
                lrs.append(tmp_lr)
        for lr_idx, group in enumerate(self.optimizer.param_groups):
            self.last_lr_grad[lr_idx] = 0
            for i, param in enumerate(group["params"]):
                self.accumulated_adam_buffer[i] = torch.zeros(param.size(), device=param.device)
        return list(lrs)

    def buffer_step(self, num_batch=1500) -> None:
        for lr_idx, group in enumerate(self.optimizer.param_groups):
            lr_grad = 0
            for i, param in enumerate(group["params"]):
                if param.grad != None:
                    lr_grad += torch.sum(torch.mul(self.accumulated_adam_buffer[i], param.grad.data))
                    grad = param.grad.data
                    exp_avg = self.optimizer.state[param]["exp_avg"].data
                    exp_avg_sq = self.optimizer.state[param]["exp_avg_sq"].data
                    step = self.optimizer.state[param]["step"]
                    beta1, beta2 = group['betas']
                    weight_decay = group['weight_decay']
                    eps = group["eps"]

                    bias_correction1 = 1 - beta1 ** step
                    bias_correction2 = 1 - beta2 ** step

                    if weight_decay != 0:
                        grad = grad.add(param, alpha=weight_decay)

                    numer = exp_avg.mul(beta1).add(grad, alpha=1 - beta1).div(bias_correction1)
                    denom = (exp_avg_sq.mul(beta2).addcmul(grad, grad, value=1 - beta2).sqrt() / math.sqrt(bias_correction2)).add(eps)
                    self.accumulated_adam_buffer[i] += torch.div(numer, denom).data.clone()
            # self.last_lr_grad[lr_idx] = self.loss_decay*self.last_lr_grad[lr_idx]+(1-self.loss_decay)/(1-self.loss_decay**num_batch)*lr_grad
            self.last_lr_grad[lr_idx] += lr_grad/num_batch
        return
