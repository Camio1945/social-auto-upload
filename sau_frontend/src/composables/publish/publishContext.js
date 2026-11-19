import { inject } from 'vue'

// 发布中心共享状态的注入标识
export const PUBLISH_KEY = Symbol('publish-center')

// 在子组件中获取发布中心共享状态
export const usePublishContext = () => inject(PUBLISH_KEY)
