<template>
  <div class="comment-management">
    <div class="comment-container">
      <div class="toolbar">
        <h3>评论管理</h3>
        <div class="toolbar-actions">
          <el-radio-group v-model="platformType" @change="changePlatform">
            <el-radio-button :value="3">抖音</el-radio-button>
            <el-radio-button :value="4">快手</el-radio-button>
          </el-radio-group>

          <el-radio-group v-model="handledFilter" @change="fetchComments">
            <el-radio-button value="">全部</el-radio-button>
            <el-radio-button value="0">未处理</el-radio-button>
            <el-radio-button value="1">已处理</el-radio-button>
          </el-radio-group>

          <el-select
            v-model="postFilter"
            placeholder="全部作品"
            clearable
            class="post-filter"
            @change="fetchComments"
          >
            <el-option
              v-for="post in posts"
              :key="post.id"
              :label="post.title || post.platformPostId"
              :value="post.id"
            />
          </el-select>

          <el-button type="primary" :loading="syncStatus.running" @click="startSync">
            <el-icon><Refresh /></el-icon>
            <span>{{ syncStatus.running ? '同步中' : '同步评论' }}</span>
          </el-button>
        </div>
      </div>

      <div class="summary">
        <el-tag :type="platformType === 3 ? 'danger' : 'warning'" effect="plain">
          {{ platformName }}
        </el-tag>
        <span>作品 {{ posts.length }} 个 · 评论 {{ totalSaved }} 条 · 未处理 {{ unhandledTotal }} 条</span>
        <span v-if="syncStatus.finishedAt && syncStatus.type === platformType" class="synced-at">
          上次同步：{{ syncStatus.finishedAt }}
          <template v-if="syncStatus.message"> · {{ syncStatus.message }}</template>
        </span>
      </div>

      <el-alert
        v-if="syncStatus.running && syncStatus.type === platformType"
        type="info"
        :closable="false"
        class="sync-alert"
        :title="syncStatus.message"
      >
        <el-progress
          v-if="syncStatus.total"
          :percentage="syncPercent"
          :stroke-width="6"
          style="margin-top: 8px"
        />
      </el-alert>
      <el-alert
        v-if="syncStatus.phase === 'error' && syncStatus.type === platformType"
        type="error"
        :closable="false"
        class="sync-alert"
        :title="syncStatus.message"
      />
      <el-alert
        v-if="!syncStatus.running && syncStatus.type === platformType
          && syncStatus.truncated && syncStatus.truncated.length"
        type="warning"
        :closable="false"
        class="sync-alert"
        :title="`有 ${syncStatus.truncated.length} 个作品的评论超过 ${maxCommentPages} 页，已截断，请到平台查看完整评论`"
      />

      <el-table v-if="comments.length > 0" :data="comments" style="width: 100%">
        <el-table-column label="作品" min-width="230">
          <template #default="scope">
            <div class="post-cell">
              <el-image
                v-if="scope.row.postCoverUrl"
                :src="scope.row.postCoverUrl"
                fit="cover"
                class="post-cover"
              />
              <a
                v-if="scope.row.postShareUrl"
                :href="scope.row.postShareUrl"
                target="_blank"
                rel="noopener"
                class="post-title"
              >
                {{ scope.row.postTitle || scope.row.platformCommentId }}
              </a>
              <span v-else class="post-title">{{ scope.row.postTitle || '-' }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="评论者" width="160">
          <template #default="scope">
            <div class="author-cell">
              <el-avatar :size="26" :src="scope.row.authorAvatar">
                {{ (scope.row.authorName || '?').slice(0, 1) }}
              </el-avatar>
              <span class="author-name">{{ scope.row.authorName || '-' }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="content" label="评论内容" min-width="260" show-overflow-tooltip />

        <el-table-column label="点赞" width="80">
          <template #default="scope">{{ scope.row.likeCount }}</template>
        </el-table-column>

        <el-table-column label="评论时间" width="170">
          <template #default="scope">{{ scope.row.platformCreatedAt || '-' }}</template>
        </el-table-column>

        <el-table-column label="已处理" width="100" fixed="right">
          <template #default="scope">
            <el-switch
              :model-value="scope.row.isHandled === 1"
              :loading="handlingId === scope.row.id"
              @change="(value) => toggleHandled(scope.row, value)"
            />
          </template>
        </el-table-column>

        <el-table-column label="操作" width="140" fixed="right">
          <template #default="scope">
            <el-button v-if="scope.row.userDigged === 1" type="info" link disabled>已赞</el-button>
            <el-button
              v-else
              type="primary"
              link
              :loading="likingId === scope.row.id"
              @click="likeComment(scope.row)"
            >点赞</el-button>
            <el-button type="primary" link @click="openReply(scope.row)">回复</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-else class="empty-data">
        <el-empty description="暂无评论，点击右上角同步评论" />
      </div>
    </div>

    <el-dialog v-model="replyVisible" title="回复评论" width="520px">
      <div class="reply-target">
        <div class="reply-author">回复 {{ replyTarget.authorName }}</div>
        <div class="reply-origin">{{ replyTarget.content }}</div>
      </div>
      <el-input
        v-model="replyText"
        type="textarea"
        :rows="4"
        :maxlength="200"
        show-word-limit
        placeholder="输入回复内容"
        @keydown.enter.prevent
        @input="normalizeReplyText"
      />
      <div class="reply-hint">仅支持文本，不能换行或 @ 用户，最多 200 字</div>
      <template #footer>
        <el-button @click="replyVisible = false">取消</el-button>
        <el-button type="primary" :loading="replying" @click="confirmReply">确认发送</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { Refresh } from '@element-plus/icons-vue'
import { useCommentManagement } from '@/composables/useCommentManagement'

const {
  comments,
  posts,
  platformType,
  platformName,
  handledFilter,
  postFilter,
  handlingId,
  replyVisible,
  replyTarget,
  replyText,
  replying,
  likingId,
  syncStatus,
  maxCommentPages,
  totalSaved,
  unhandledTotal,
  syncPercent,
  changePlatform,
  fetchComments,
  startSync,
  toggleHandled,
  openReply,
  likeComment,
  normalizeReplyText,
  confirmReply
} = useCommentManagement()
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.comment-management {
  .comment-container {
    background-color: var(--el-bg-color);
    border-radius: 4px;
    box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
    padding: 20px;

    .toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 16px;

      h3 {
        margin: 0;
        font-size: 16px;
        font-weight: 500;
        color: var(--el-text-color-primary);
      }

      .toolbar-actions {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;

        .post-filter {
          width: 240px;
        }
      }
    }

    .summary {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
      padding: 10px 12px;
      margin-bottom: 16px;
      border-radius: 4px;
      background-color: var(--el-fill-color-light);
      font-size: 13px;
      color: var(--el-text-color-regular);

      .synced-at {
        margin-left: auto;
        color: var(--el-text-color-secondary);
      }
    }

    .sync-alert {
      margin-bottom: 16px;
    }

    .post-cell {
      display: flex;
      align-items: center;
      gap: 10px;

      .post-cover {
        width: 40px;
        height: 40px;
        border-radius: 4px;
        flex-shrink: 0;
      }

      .post-title {
        color: var(--el-text-color-primary);
        text-decoration: none;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;

        &:hover {
          color: var(--el-color-primary);
        }
      }
    }

    .author-cell {
      display: flex;
      align-items: center;
      gap: 8px;

      .author-name {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    .empty-data {
      padding: 40px 0;
    }
  }

  .reply-target {
    padding: 10px 12px;
    margin-bottom: 12px;
    border-radius: 4px;
    background-color: var(--el-fill-color-light);

    .reply-author {
      margin-bottom: 6px;
      font-size: 13px;
      color: var(--el-text-color-secondary);
    }

    .reply-origin {
      font-size: 14px;
      color: var(--el-text-color-primary);
      word-break: break-word;
    }
  }

  .reply-hint {
    margin-top: 8px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
}
</style>
